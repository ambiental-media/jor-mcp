"""Rate-limiting ASGI middleware using Redis Fixed Window algorithm.

This middleware must be placed after AuthMiddleware in the middleware
stack.  It reads ``scope["user"]["uid"]`` and ``scope["user"]["tier"]``
injected by AuthMiddleware, then enforces per-tier monthly quotas stored
in Redis.

The Fixed Window algorithm uses a simple INCR counter per user per billing
month (key: ``rl:{uid}:YYYY-MM``).  When a new key is created (INCR returns
1), an EXPIRE is set to the exact start of the next calendar month so the
counter resets cleanly on the billing date without accumulating stale data.

Fail-open policy: if Redis is unreachable or times out, the request is
allowed through and the failure is logged for observability.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import RATE_LIMIT_BASIC, RATE_LIMIT_PRO

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"

_TIER_QUOTAS: dict[str, int] = {
    "basic": RATE_LIMIT_BASIC,
    "pro": RATE_LIMIT_PRO,
}
"""Map of tier name -> max_requests_per_month."""


class RateLimitMiddleware:
    """ASGI middleware that enforces per-user, per-tier monthly rate limits via Redis.

    Uses the Fixed Window algorithm: for each request an integer counter is
    maintained in Redis keyed by ``rl:{uid}:YYYY-MM``.  The counter is
    incremented atomically with INCR and expires at the start of the next
    calendar month, guaranteeing that limits reset cleanly on the billing date.

    On Redis failure the middleware is fail-open: a warning is logged and the
    request is forwarded to the next layer unchanged.

    The ``/health`` path is exempt from rate limiting.
    """

    def __init__(self, app: ASGIApp, redis_factory: Callable[[], Redis]) -> None:
        self.app = app
        self._redis_factory: Callable[[], Redis] = redis_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope.get("path") == _HEALTH_PATH:
            await self.app(scope, receive, send)
            return

        user: dict[str, str] | None = scope.get("user")
        if not user:
            # AuthMiddleware already rejected the request upstream; pass through.
            await self.app(scope, receive, send)
            return

        uid: str = user["uid"]
        tier: str = user.get("tier", "basic")
        max_requests: int = _TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)

        try:
            redis_client = self._redis_factory()
            allowed, retry_after = await _check_fixed_window(redis_client, uid, max_requests)
        except (RedisError, RuntimeError) as exc:
            logger.warning(
                "Redis rate-limit check failed; failing open",
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
    redis: Redis,
    uid: str,
    max_requests: int,
) -> tuple[bool, int]:
    """Apply the Fixed Window algorithm against Redis.

    Uses a single atomic INCR per request.  If this is the first request in
    the current billing cycle (count == 1), an EXPIRE is set so the key is
    automatically removed at the start of next month.

    Args:
        redis: An active async Redis client.
        uid: The unique user identifier (used as part of the Redis key).
        max_requests: Maximum number of requests allowed within the month.

    Returns:
        A tuple of (allowed, retry_after_seconds).  When allowed is True,
        retry_after is 0.  When False, retry_after indicates how many seconds
        remain until the billing window resets (start of next month).
    """
    now = datetime.now(UTC)
    key = f"rl:{uid}:{now.strftime('%Y-%m')}"

    count: int = await redis.incr(key)

    if count == 1:
        # New billing cycle: set key to expire at the start of next month.
        expire_seconds = _seconds_until_next_month(now)
        await redis.expire(key, expire_seconds)

    if count > max_requests:
        retry_after = _seconds_until_next_month(now)
        return False, retry_after

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
