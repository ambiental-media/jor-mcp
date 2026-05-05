"""Rate-limiting ASGI middleware using Redis Sliding Window algorithm.

This middleware must be placed after AuthMiddleware in the middleware
stack.  It reads ``scope["user"]["uid"]`` and ``scope["user"]["tier"]``
injected by AuthMiddleware, then enforces per-tier quotas stored in Redis.

Fail-open policy: if Redis is unreachable or times out, the request is
allowed through and the failure is logged for observability.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from redis.asyncio import Redis
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import RATE_LIMIT_BASIC, RATE_LIMIT_PRO

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"

_TIER_QUOTAS: dict[str, tuple[int, int]] = {
    "basic": RATE_LIMIT_BASIC,
    "pro": RATE_LIMIT_PRO,
}
"""Map of tier name -> (max_requests, window_seconds)."""


class RateLimitMiddleware:
    """ASGI middleware that enforces per-user, per-tier rate limits via Redis.

    Uses the Sliding Window algorithm: for each request a sorted set is
    maintained in Redis keyed by ``rl:{uid}``.  Timestamps of prior requests
    within the current window are stored as members; members older than the
    window are pruned on every call so the cardinality always reflects the
    true request count within the sliding window.

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
        max_requests, window_seconds = _TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)

        try:
            redis_client = self._redis_factory()
            allowed, retry_after = await _check_sliding_window(
                redis_client, uid, max_requests, window_seconds
            )
        except Exception as exc:
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


async def _check_sliding_window(
    redis: Redis,
    uid: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Apply the Sliding Window algorithm against Redis.

    Args:
        redis: An active async Redis client.
        uid: The unique user identifier (used as part of the Redis key).
        max_requests: Maximum number of requests allowed within the window.
        window_seconds: Duration of the sliding window in seconds.

    Returns:
        A tuple of (allowed, retry_after_seconds).  When allowed is True,
        retry_after is 0.  When False, retry_after indicates how many seconds
        the caller should wait before retrying.
    """
    now_ms = int(time.time() * 1000)
    window_ms = window_seconds * 1000
    cutoff_ms = now_ms - window_ms
    key = f"rl:{uid}"

    pipe = redis.pipeline()
    # Remove timestamps outside the current window
    pipe.zremrangebyscore(key, "-inf", cutoff_ms)
    # Count remaining (within window) BEFORE adding this request
    pipe.zcard(key)
    # Add current timestamp (use ms timestamp as both score and member;
    # append uid to avoid score collisions in high-concurrency scenarios)
    pipe.zadd(key, {f"{now_ms}-{uid}": now_ms})
    # Expire the key after the window so Redis doesn't accumulate stale keys
    pipe.expire(key, window_seconds + 1)
    results: list[Any] = await pipe.execute()

    count_before: int = int(results[1])

    if count_before >= max_requests:
        # Calculate the oldest timestamp still in the window to determine
        # how long the caller must wait for a slot to free up.
        oldest: list[tuple[bytes, float]] = await redis.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_ms = int(oldest[0][1])
            retry_after = max(1, ((oldest_ms + window_ms) - now_ms) // 1000)
        else:
            retry_after = window_seconds
        return False, int(retry_after)

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
