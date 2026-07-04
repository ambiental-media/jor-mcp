"""Rate-limiting ASGI middleware using Firestore Fixed Window algorithm.

This middleware must be placed after AuthMiddleware in the middleware
stack. It reads ``scope["user"]["uid"]`` and ``scope["user"]["tier"]``
injected by AuthMiddleware, then enforces per-tier monthly quotas stored
in Firestore.

The Fixed Window algorithm uses one document per user per month in the
``rate_limits`` collection (document id: ``{uid}_YYYY-MM``). Each request
atomically increments the document's ``count`` field with
``firestore.Increment(1)`` and reads the new value back; the request is
rejected once that value exceeds the tier quota. The server-side Increment
is atomic, so concurrent Cloud Run replicas processing the same uid never
lose updates.

Fail-open policy: if Firestore is unreachable or times out, the request is
allowed through and the failure is logged for observability.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import RATE_LIMIT_BASIC, RATE_LIMIT_COLLECTION, RATE_LIMIT_PRO

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"

_TIER_QUOTAS: dict[str, int] = {
    "basic": RATE_LIMIT_BASIC,
    "pro": RATE_LIMIT_PRO,
}
"""Map of tier name -> max_requests_per_month."""


class RateLimitMiddleware:
    """ASGI middleware that enforces per-user, per-tier monthly rate limits via Firestore.

    Uses the Fixed Window algorithm: for each request an integer counter is
    maintained in Firestore document ``rate_limits/{uid}_YYYY-MM``. The counter
    is incremented atomically with ``firestore.Increment(1)`` and the request is
    rejected once the value exceeds the tier quota.

    On Firestore failure the middleware is fail-open: a warning is logged and the
    request is forwarded to the next layer unchanged.

    The ``/health`` path is exempt from rate limiting.
    """

    def __init__(self, app: ASGIApp, firestore_factory: Callable[[], AsyncClient]) -> None:
        self.app = app
        self._firestore_factory: Callable[[], AsyncClient] = firestore_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope.get("path") == _HEALTH_PATH:
            await self.app(scope, receive, send)
            return

        user: dict[str, str] | None = scope.get("user")
        if not user:
            # AuthMiddleware bypassed authentication (no authenticated user present); pass through.
            await self.app(scope, receive, send)
            return

        uid: str = user["uid"]
        tier: str = user.get("tier", "basic")
        max_requests: int = _TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)

        try:
            firestore_client = self._firestore_factory()
            allowed, retry_after = await _check_fixed_window(firestore_client, uid, max_requests)
        except (gcp_exceptions.GoogleAPICallError, gcp_exceptions.RetryError, RuntimeError) as exc:
            logger.warning(
                "Firestore rate-limit check failed; failing open",
                extra={"uid": uid, "error": str(exc)},
            )
            await self.app(scope, receive, send)
            return

        if not allowed:
            await _send_too_many_requests(send, retry_after)
            return

        await self.app(scope, receive, send)


def _seconds_until_next_month(now: datetime) -> int:
    """Calculate the number of seconds from *now* until the start of next month.

    Args:
        now: A timezone-aware datetime representing the current instant.

    Returns:
        Number of seconds until midnight UTC on the first day of the next
        calendar month, minimum 1.
    """
    if now.month == 12:
        next_month_start = now.replace(
            year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        next_month_start = now.replace(
            month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    return max(1, int((next_month_start - now).total_seconds()))


async def _check_fixed_window(
    firestore_client: AsyncClient,
    uid: str,
    max_requests: int,
) -> tuple[bool, int]:
    """Apply the Fixed Window algorithm against Firestore using an atomic Increment.

    Increments the ``count`` field of ``rate_limits/{uid}_YYYY-MM`` with
    ``firestore.Increment(1)`` (creating the document on the first request of
    the month) and reads the new value back. The request is rejected when the
    post-increment value exceeds the monthly quota. The server-side Increment is
    atomic, so concurrent replicas processing the same uid never lose updates.

    Args:
        firestore_client: An active async Firestore client.
        uid: The unique user identifier (used as part of the document id).
        max_requests: Maximum number of requests allowed within the month.

    Returns:
        A tuple of (allowed, retry_after_seconds).  When allowed is True,
        retry_after is 0.  When False, retry_after indicates how many seconds
        remain until the billing window resets (start of next month).
    """
    now = datetime.now(UTC)
    month_key = now.strftime("%Y-%m")
    doc_id = f"{uid}_{month_key}"
    doc_ref = firestore_client.collection(RATE_LIMIT_COLLECTION).document(doc_id)

    await doc_ref.set(
        {
            "uid": uid,
            "month": month_key,
            "count": firestore.Increment(1),
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    snapshot = await doc_ref.get()
    current_count = int(snapshot.get("count") or 0)

    if current_count > max_requests:
        return False, _seconds_until_next_month(now)
    return True, 0


async def _send_too_many_requests(send: Send, retry_after: int) -> None:
    """Emit an HTTP 429 Too Many Requests ASGI response.

    Args:
        send: The ASGI send callable.
        retry_after: Seconds the client should wait before retrying.
    """
    headers = [
        (b"content-type", b"application/json"),
        (b"retry-after", str(retry_after).encode()),
    ]
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail": "Too Many Requests"}',
            "more_body": False,
        }
    )
