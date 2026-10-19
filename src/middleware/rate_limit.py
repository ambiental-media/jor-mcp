"""Rate-limiting ASGI middleware using Firestore Fixed Window algorithm.

This middleware must be placed after AuthMiddleware in the middleware
stack. It reads ``scope["user"]["uid"]`` and ``scope["user"]["tier"]``
injected by AuthMiddleware, then enforces per-tier weekly token quotas
stored in Firestore.

The Fixed Window algorithm uses one document per user per ISO week in the
``rate_limits`` collection (document id: ``{uid}_YYYY-Www``). Quotas are
charged in tokens rather than requests: the middleware measures the request
and response payloads exchanged with the client and converts that volume
through :func:`src.token_usage.estimate_tokens`.

Quota is checked before the request runs and charged after it completes,
because the cost is only known once the response has been produced. A caller
sitting just under the limit can therefore overshoot it with a single large
response; the following request is rejected. Charging first would require
guessing the cost in advance, which is worse.

Fail-open policy: if Firestore is unreachable or times out, the request is
allowed through and the failure is logged for observability.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import RATE_LIMIT_COLLECTION, TIER_QUOTAS
from src.token_usage import estimate_tokens

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"

_FIRESTORE_ERRORS = (
    gcp_exceptions.GoogleAPICallError,
    gcp_exceptions.RetryError,
    RuntimeError,
)


class RateLimitMiddleware:
    """ASGI middleware that enforces per-user, per-tier weekly token quotas via Firestore.

    Uses the Fixed Window algorithm: for each user an integer counter is
    maintained in Firestore document ``rate_limits/{uid}_YYYY-Www``. The counter
    holds estimated tokens, is incremented atomically with
    ``firestore.Increment`` once the response has been produced, and the next
    request is rejected when the stored value has reached the tier quota.

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

        # AuthMiddleware rejects any token whose tier is missing or unknown, so
        # both lookups are guaranteed to resolve here.
        uid: str = user["uid"]
        max_tokens: int = TIER_QUOTAS[user["tier"]]
        now = datetime.now(UTC)

        try:
            firestore_client = self._firestore_factory()
            used_tokens = await _read_usage(firestore_client, uid, _week_key(now))
        except _FIRESTORE_ERRORS as exc:
            logger.warning(
                "Firestore rate-limit check failed; failing open",
                extra={"uid": uid, "error": str(exc)},
            )
            await self.app(scope, receive, send)
            return

        if used_tokens >= max_tokens:
            await send_too_many_requests(send, _seconds_until_next_week(now))
            return

        meter = _PayloadMeter()
        await self.app(scope, meter.wrap_receive(receive), meter.wrap_send(send))

        if meter.tokens:
            await _record_usage(firestore_client, uid, _week_key(now), meter.tokens)


class _PayloadMeter:
    """Accumulate the token cost of the payloads flowing through one request.

    Wraps the ASGI ``receive`` and ``send`` callables so that every body chunk
    is measured in passing, without buffering it: only the running total is
    kept. Streaming responses are therefore charged in full once the stream
    ends, not per chunk.
    """

    def __init__(self) -> None:
        self.tokens = 0

    def wrap_receive(self, receive: Receive) -> Receive:
        async def counting_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request":
                self.tokens += estimate_tokens(message.get("body", b""))
            return message

        return counting_receive

    def wrap_send(self, send: Send) -> Send:
        async def counting_send(message: Message) -> None:
            if message["type"] == "http.response.body":
                self.tokens += estimate_tokens(message.get("body", b""))
            await send(message)

        return counting_send


def _week_key(now: datetime) -> str:
    """Return the ISO week identifier (``YYYY-Www``) *now* falls into.

    Args:
        now: A timezone-aware datetime representing the current instant.

    Returns:
        The ISO-8601 week key, e.g. ``2026-W40``. The year is the ISO year,
        which differs from the calendar year for days at a year boundary.
    """
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _seconds_until_next_week(now: datetime) -> int:
    """Calculate the number of seconds from *now* until the next window opens.

    Args:
        now: A timezone-aware datetime representing the current instant.

    Returns:
        Number of seconds until midnight UTC on the coming Monday, minimum 1.
    """
    days_ahead = 8 - now.isoweekday()
    next_week_start = (now + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((next_week_start - now).total_seconds()))


async def _read_usage(firestore_client: AsyncClient, uid: str, week_key: str) -> int:
    """Return how many tokens *uid* has already consumed within *week_key*.

    Args:
        firestore_client: An active async Firestore client.
        uid: The unique user identifier (used as part of the document id).
        week_key: The ISO week identifier produced by :func:`_week_key`.

    Returns:
        The stored token count, or 0 when the window has no document yet.
    """
    doc_ref = firestore_client.collection(RATE_LIMIT_COLLECTION).document(f"{uid}_{week_key}")
    snapshot = await doc_ref.get()
    if not snapshot.exists:
        return 0
    return int(snapshot.get("tokens") or 0)


async def _record_usage(
    firestore_client: AsyncClient,
    uid: str,
    week_key: str,
    tokens: int,
) -> None:
    """Charge *tokens* against the window counter, creating it when absent.

    Uses ``firestore.Increment`` so concurrent Cloud Run replicas serving the
    same uid never lose updates. Failures are swallowed after logging: a request
    already served must not turn into an error because its accounting did not
    persist.

    Args:
        firestore_client: An active async Firestore client.
        uid: The unique user identifier (used as part of the document id).
        week_key: The ISO week identifier produced by :func:`_week_key`.
        tokens: Estimated tokens consumed by the request that just completed.
    """
    doc_ref = firestore_client.collection(RATE_LIMIT_COLLECTION).document(f"{uid}_{week_key}")
    try:
        await doc_ref.set(
            {
                "uid": uid,
                "week": week_key,
                "tokens": firestore.Increment(tokens),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except _FIRESTORE_ERRORS as exc:
        logger.warning(
            "Firestore token accounting failed; usage not recorded",
            extra={"uid": uid, "week": week_key, "tokens": tokens, "error": str(exc)},
        )


async def send_too_many_requests(send: Send, retry_after: int) -> None:
    """Emit an HTTP 429 Too Many Requests ASGI response.

    Shared with :mod:`src.middleware.ip_rate_limit` so both limiters answer
    rejected callers with an identical payload and ``Retry-After`` contract.

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
