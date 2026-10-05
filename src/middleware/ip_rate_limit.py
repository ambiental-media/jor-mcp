"""IP-based rate-limiting ASGI middleware for unauthenticated routes.

The OAuth discovery (``/.well-known``) and proxy (``/api/oauth``) routes are
deliberately exempt from :class:`~src.middleware.auth.AuthMiddleware`: they are
the mechanism through which clients obtain Firebase tokens. That leaves
``POST /api/oauth/register`` (RFC 7591 Dynamic Client Registration) writable by
anyone on the internet, which would let an attacker flood Firestore with orphan
client documents. This middleware closes that gap by counting requests per
client IP before they reach the routers.

The window is intentionally short (default: 60 requests per 60 seconds), unlike
the monthly per-user quota enforced by :class:`~src.middleware.rate_limit.RateLimitMiddleware`.
Counters live in the ``ip_rate_limits`` Firestore collection, one document per
IP per window (document id: ``{sanitized-ip}_{window-start-epoch}``), and are
incremented atomically with ``firestore.Increment(1)`` so concurrent Cloud Run
replicas never lose updates. Each document carries an ``expires_at`` field so a
Firestore TTL policy can reclaim expired windows automatically.

Fail-open policy: if Firestore is unreachable the request is allowed through and
the failure is logged, matching the per-user limiter's behaviour.
"""

import ipaddress
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient
from starlette.types import ASGIApp, Receive, Scope, Send

from src.api.oauth import is_oauth_path
from src.config import (
    IP_RATE_LIMIT_COLLECTION,
    IP_RATE_LIMIT_REQUESTS,
    IP_RATE_LIMIT_TRUSTED_PROXIES,
    IP_RATE_LIMIT_WINDOW_SECONDS,
)
from src.middleware.rate_limit import send_too_many_requests

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"
_OAUTH_HEALTH_PATH = "/api/oauth/health"

_UNKNOWN_IP = "unknown"
"""Bucket used when no usable client IP can be derived from the request."""


class IPRateLimitMiddleware:
    """ASGI middleware enforcing a short per-IP fixed window on unauthenticated routes.

    Only paths that :func:`src.api.oauth.is_oauth_path` reports as auth-exempt are
    metered — authenticated traffic is already covered by the per-user monthly
    quota, and health routes (``/health``, ``/api/oauth/health``) stay open for probes.

    On Firestore failure the middleware is fail-open: a warning is logged and the
    request is forwarded to the next layer unchanged.
    """

    def __init__(self, app: ASGIApp, firestore_factory: Callable[[], AsyncClient]) -> None:
        self.app = app
        self._firestore_factory: Callable[[], AsyncClient] = firestore_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if path in (_HEALTH_PATH, _OAUTH_HEALTH_PATH) or not is_oauth_path(path):
            await self.app(scope, receive, send)
            return

        client_ip = _extract_client_ip(scope)

        try:
            firestore_client = self._firestore_factory()
            allowed, retry_after = await _check_ip_fixed_window(firestore_client, client_ip)
        except (gcp_exceptions.GoogleAPICallError, gcp_exceptions.RetryError, RuntimeError) as exc:
            logger.warning(
                "Firestore IP rate-limit check failed; failing open",
                extra={"client_ip": client_ip, "path": path, "error": str(exc)},
            )
            await self.app(scope, receive, send)
            return

        if not allowed:
            logger.warning(
                "IP rate limit exceeded on unauthenticated route",
                extra={"client_ip": client_ip, "path": path},
            )
            await send_too_many_requests(send, retry_after)
            return

        await self.app(scope, receive, send)


def _normalize_ip(value: str) -> str | None:
    """Parse *value* into a canonical IP address string.

    Strips an optional port and IPv6 brackets, then validates the remainder.
    Validation matters because ``X-Forwarded-For`` is caller-supplied: an
    unvalidated value would end up in a Firestore document id.

    Args:
        value: A raw address such as ``"203.0.113.7"``, ``"203.0.113.7:443"`` or
            ``"[2001:db8::1]:443"``.

    Returns:
        The compressed IP address, or None when *value* is not a valid address.
    """
    candidate = value.strip()
    if candidate.startswith("["):
        candidate = candidate[1:].partition("]")[0]
    elif candidate.count(":") == 1:
        candidate = candidate.partition(":")[0]
    try:
        return ipaddress.ip_address(candidate).compressed
    except ValueError:
        return None


def _extract_client_ip(scope: Scope) -> str:
    """Derive the originating client IP from the ASGI scope.

    Prefers ``X-Forwarded-For``, reading it from the right so that entries
    forged by the caller are ignored (see :data:`IP_RATE_LIMIT_TRUSTED_PROXIES`).
    Falls back to the ASGI ``client`` tuple — the direct peer address, which is
    what ``request.client.host`` exposes — and finally to a shared
    ``"unknown"`` bucket.

    Args:
        scope: The ASGI connection scope.

    Returns:
        A canonical IP address string, or ``"unknown"``.
    """
    raw_headers = cast(list[tuple[bytes, bytes]], scope.get("headers", []))
    header_map: dict[bytes, bytes] = {k.lower(): v for k, v in raw_headers}
    forwarded_for = header_map.get(b"x-forwarded-for", b"").decode("utf-8", errors="ignore")

    hops = [entry for entry in (part.strip() for part in forwarded_for.split(",")) if entry]
    position = IP_RATE_LIMIT_TRUSTED_PROXIES + 1
    if len(hops) >= position:
        forwarded_ip = _normalize_ip(hops[-position])
        if forwarded_ip is not None:
            return forwarded_ip

    client = scope.get("client")
    if client:
        peer_ip = _normalize_ip(str(client[0]))
        if peer_ip is not None:
            return peer_ip

    return _UNKNOWN_IP


def _window_bounds(now: datetime) -> tuple[int, int]:
    """Return the epoch start and end of the fixed window containing *now*.

    Windows are aligned to the Unix epoch so every replica computes identical
    boundaries without coordination.

    Args:
        now: A timezone-aware datetime representing the current instant.

    Returns:
        A tuple of (window_start_epoch, window_end_epoch) in seconds.
    """
    epoch_seconds = int(now.timestamp())
    window_seconds = max(1, IP_RATE_LIMIT_WINDOW_SECONDS)
    window_start = epoch_seconds - (epoch_seconds % window_seconds)
    return window_start, window_start + window_seconds


async def _check_ip_fixed_window(
    firestore_client: AsyncClient,
    client_ip: str,
) -> tuple[bool, int]:
    """Apply the per-IP Fixed Window algorithm against Firestore.

    Increments the ``count`` field of ``ip_rate_limits/{sanitized-ip}_{window-start}``
    with ``firestore.Increment(1)`` (creating the document on the first request of
    the window) and reads the new value back. The request is rejected when the
    post-increment value exceeds :data:`IP_RATE_LIMIT_REQUESTS`.

    Args:
        firestore_client: An active async Firestore client.
        client_ip: The canonical client IP address.

    Returns:
        A tuple of (allowed, retry_after_seconds). When allowed is True,
        retry_after is 0. When False, retry_after is the number of seconds left
        until the current window closes.
    """
    now = datetime.now(UTC)
    window_start, window_end = _window_bounds(now)
    # ':' and '.' are legal in document ids but make the id awkward to query by hand.
    doc_id = f"{client_ip.replace(':', '-').replace('.', '-')}_{window_start}"
    doc_ref = firestore_client.collection(IP_RATE_LIMIT_COLLECTION).document(doc_id)

    await doc_ref.set(
        {
            "ip": client_ip,
            "window_start": window_start,
            "count": firestore.Increment(1),
            "updated_at": firestore.SERVER_TIMESTAMP,
            "expires_at": datetime.fromtimestamp(window_end, UTC),
        },
        merge=True,
    )
    snapshot = await doc_ref.get()
    current_count = int(snapshot.get("count") or 0)

    if current_count > IP_RATE_LIMIT_REQUESTS:
        return False, max(1, window_end - int(now.timestamp()))
    return True, 0
