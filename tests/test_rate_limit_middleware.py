"""Unit tests for RateLimitMiddleware.

Uses the "Spy App" pattern to inspect internal state mutations and direct
async middleware calls.  The Redis client is always mocked so no real Redis
instance is required.
"""

from collections.abc import MutableMapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis import exceptions as redis_exceptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scope(path: str = "/mcp/", uid: str = "user-1", tier: str = "basic") -> dict[str, Any]:
    """Build a minimal ASGI HTTP scope with a pre-populated user dict."""
    return {
        "type": "http",
        "path": path,
        "headers": [],
        "user": {"uid": uid, "tier": tier},
    }


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_redis_mock(*, count: int = 1) -> MagicMock:
    """Build a Redis mock whose INCR returns *count*.

    Args:
        count: The value returned by ``redis.incr()``, representing the total
            number of requests for the current billing cycle after this one is
            counted.
    """
    redis_mock = MagicMock()
    redis_mock.incr = AsyncMock(return_value=count)
    redis_mock.expire = AsyncMock(return_value=True)
    return redis_mock


# ---------------------------------------------------------------------------
# Bypass tests
# ---------------------------------------------------------------------------


async def test_health_path_bypasses_rate_limit() -> None:
    """/health requests pass through without touching Redis."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock()
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    scope: dict[str, Any] = {"type": "http", "path": "/health", "headers": []}

    await middleware(scope, _noop_receive, AsyncMock())

    assert called["app"] is True
    redis_mock.incr.assert_not_called()


async def test_non_http_scope_passes_through() -> None:
    """Lifespan and other non-HTTP scopes bypass rate limiting."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock()
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    await middleware({"type": "lifespan"}, _noop_receive, AsyncMock())

    assert called["app"] is True
    redis_mock.incr.assert_not_called()


async def test_missing_user_scope_passes_through() -> None:
    """Requests without scope['user'] (already rejected by AuthMiddleware) pass through."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock()
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    scope: dict[str, Any] = {"type": "http", "path": "/mcp/", "headers": []}

    await middleware(scope, _noop_receive, AsyncMock())

    assert called["app"] is True
    redis_mock.incr.assert_not_called()


# ---------------------------------------------------------------------------
# Allowed request tests
# ---------------------------------------------------------------------------


async def test_request_within_limit_is_allowed() -> None:
    """A request under quota reaches the inner application."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=5)  # well below any tier monthly limit
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    await middleware(_make_scope(tier="basic"), _noop_receive, AsyncMock())

    assert called["app"] is True


@pytest.mark.parametrize("tier", ["basic", "pro"])
async def test_first_request_always_allowed(tier: str) -> None:
    """The very first request of a billing cycle (count=1) is always allowed."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=1)
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    await middleware(_make_scope(tier=tier), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_first_request_sets_expire() -> None:
    """When count==1 (new billing cycle), EXPIRE is set on the Redis key."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=1)

    middleware = RateLimitMiddleware(AsyncMock(), lambda: redis_mock)
    await middleware(_make_scope(), _noop_receive, AsyncMock())

    redis_mock.expire.assert_called_once()


async def test_subsequent_request_does_not_set_expire() -> None:
    """When count > 1 (existing key), EXPIRE is not called again."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=2)

    middleware = RateLimitMiddleware(AsyncMock(), lambda: redis_mock)
    await middleware(_make_scope(), _noop_receive, AsyncMock())

    redis_mock.expire.assert_not_called()


# ---------------------------------------------------------------------------
# Rate-limit exceeded tests
# ---------------------------------------------------------------------------


async def test_request_over_limit_returns_429() -> None:
    """When count > limit, the middleware short-circuits with HTTP 429."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    await middleware(_make_scope(tier="basic"), _noop_receive, capture_send)

    assert called["app"] is False
    assert responses[0]["status"] == 429
    # Retry-After header must be present
    headers = dict(responses[0]["headers"])
    assert b"retry-after" in headers


async def test_429_response_includes_retry_after_header() -> None:
    """The Retry-After header value is a positive integer string."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: redis_mock)
    await middleware(_make_scope(tier="basic"), _noop_receive, capture_send)

    assert responses[0]["status"] == 429
    headers = dict(responses[0]["headers"])
    retry_after_value = int(headers[b"retry-after"])
    assert retry_after_value >= 1


async def test_pro_tier_has_higher_limit_than_basic() -> None:
    """Pro-tier users are allowed more requests per month than basic-tier users."""
    from src.config import RATE_LIMIT_BASIC, RATE_LIMIT_PRO

    assert RATE_LIMIT_PRO > RATE_LIMIT_BASIC


async def test_basic_tier_limit_is_enforced() -> None:
    """Exactly one over the basic monthly limit, the request is blocked."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: redis_mock)
    await middleware(_make_scope(tier="basic"), _noop_receive, capture_send)

    assert responses[0]["status"] == 429


async def test_pro_tier_limit_is_enforced() -> None:
    """Exactly one over the pro monthly limit, the request is blocked."""
    from src.config import RATE_LIMIT_PRO
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=RATE_LIMIT_PRO + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: redis_mock)
    await middleware(_make_scope(tier="pro"), _noop_receive, capture_send)

    assert responses[0]["status"] == 429


async def test_unknown_tier_falls_back_to_basic_limit() -> None:
    """An unrecognised tier string defaults to basic-tier monthly quota."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = _make_redis_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: redis_mock)
    await middleware(_make_scope(tier="enterprise"), _noop_receive, capture_send)

    assert responses[0]["status"] == 429


# ---------------------------------------------------------------------------
# Fail-open (Redis unavailable) tests
# ---------------------------------------------------------------------------


async def test_redis_exception_fails_open() -> None:
    """When Redis raises a RedisError the request passes through (fail-open)."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = MagicMock()
    redis_mock.incr = AsyncMock(side_effect=redis_exceptions.ConnectionError("Redis unreachable"))

    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)

    with patch("src.middleware.rate_limit.logger") as mock_logger:
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True
    mock_logger.warning.assert_called_once()


async def test_redis_timeout_fails_open() -> None:
    """A redis TimeoutError also triggers fail-open behaviour."""
    from src.middleware.rate_limit import RateLimitMiddleware

    redis_mock = MagicMock()
    redis_mock.incr = AsyncMock(side_effect=redis_exceptions.TimeoutError("timed out"))

    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: redis_mock)
    await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_redis_factory_exception_fails_open() -> None:
    """If the redis factory itself raises (e.g. before lifespan), fail-open."""
    from src.middleware.rate_limit import RateLimitMiddleware

    def broken_factory() -> Any:
        raise RuntimeError("not initialised")

    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, broken_factory)

    with patch("src.middleware.rate_limit.logger") as mock_logger:
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True
    mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# get_redis_client tests (src/server.py)
# ---------------------------------------------------------------------------


def test_get_redis_client_raises_before_lifespan() -> None:
    """get_redis_client() raises RuntimeError when called outside lifespan."""
    import src.server as server_module
    from src.server import get_redis_client

    original = server_module._redis_client
    try:
        server_module._redis_client = None
        with pytest.raises(RuntimeError, match="not initialized"):
            get_redis_client()
    finally:
        server_module._redis_client = original
