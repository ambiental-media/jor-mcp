"""Unit tests for RateLimitMiddleware.

Uses the "Spy App" pattern to inspect internal state mutations and direct
async middleware calls. The Firestore client is always mocked so no real
Firestore access is required.
"""

from collections.abc import MutableMapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as gcp_exceptions

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


def _make_firestore_mock(*, count: int = 1) -> tuple[MagicMock, MagicMock]:
    """Build a Firestore client mock whose post-increment count resolves to *count*.

    ``count`` is the value returned by the document read that follows the atomic
    ``firestore.Increment(1)`` write, i.e. the count *after* this request.
    """
    firestore_client = MagicMock()
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.get.return_value = count

    doc_ref.set = AsyncMock(return_value=None)
    doc_ref.get = AsyncMock(return_value=snapshot)

    collection_ref = MagicMock()
    collection_ref.document.return_value = doc_ref
    firestore_client.collection.return_value = collection_ref

    return firestore_client, doc_ref


# ---------------------------------------------------------------------------
# Bypass tests
# ---------------------------------------------------------------------------


async def test_health_path_bypasses_rate_limit() -> None:
    """/health requests pass through without touching Firestore."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock()
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    scope: dict[str, Any] = {"type": "http", "path": "/health", "headers": []}

    await middleware(scope, _noop_receive, AsyncMock())

    assert called["app"] is True
    doc_ref.set.assert_not_called()


async def test_non_http_scope_passes_through() -> None:
    """Lifespan and other non-HTTP scopes bypass rate limiting."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock()
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware({"type": "lifespan"}, _noop_receive, AsyncMock())

    assert called["app"] is True
    doc_ref.set.assert_not_called()


async def test_missing_user_scope_passes_through() -> None:
    """Requests without scope['user'] (already rejected by AuthMiddleware) pass through."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock()
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    scope: dict[str, Any] = {"type": "http", "path": "/mcp/", "headers": []}

    await middleware(scope, _noop_receive, AsyncMock())

    assert called["app"] is True
    doc_ref.set.assert_not_called()


# ---------------------------------------------------------------------------
# Allowed request tests
# ---------------------------------------------------------------------------


async def test_request_within_limit_is_allowed() -> None:
    """A request under quota reaches the inner application."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=5)
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    with patch.dict("src.middleware.rate_limit._TIER_QUOTAS", {"basic": 500}):
        await middleware(_make_scope(tier="basic"), _noop_receive, AsyncMock())

    assert called["app"] is True


@pytest.mark.parametrize("tier", ["basic", "pro"])
async def test_first_request_always_allowed(tier: str) -> None:
    """The very first request of a billing cycle (count=1) is always allowed."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=1)
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware(_make_scope(tier=tier), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_uses_monthly_document_id() -> None:
    """Document id follows the {uid}_YYYY-MM fixed monthly window convention."""
    from datetime import UTC, datetime

    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=1)
    fixed_now = datetime(2026, 5, 20, 12, 30, tzinfo=UTC)

    middleware = RateLimitMiddleware(AsyncMock(), lambda: firestore_client)

    with patch("src.middleware.rate_limit.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        await middleware(_make_scope(uid="abc-123"), _noop_receive, AsyncMock())

    firestore_client.collection.return_value.document.assert_called_once_with("abc-123_2026-05")


async def test_uses_atomic_increment_for_count() -> None:
    """Rate-limit check increments the counter with firestore.Increment(1)."""
    from google.cloud import firestore

    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)
    middleware = RateLimitMiddleware(AsyncMock(), lambda: firestore_client)

    await middleware(_make_scope(), _noop_receive, AsyncMock())

    doc_ref.set.assert_awaited_once()
    payload = doc_ref.set.call_args.args[0]
    assert isinstance(payload["count"], type(firestore.Increment(1)))
    assert doc_ref.set.call_args.kwargs["merge"] is True
    doc_ref.get.assert_awaited_once()


# ---------------------------------------------------------------------------
# Rate-limit exceeded tests
# ---------------------------------------------------------------------------


async def test_request_over_limit_returns_429() -> None:
    """When the post-increment count exceeds the limit, the middleware returns HTTP 429."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware(_make_scope(tier="basic"), _noop_receive, capture_send)

    assert called["app"] is False
    assert responses[0]["status"] == 429
    headers = dict(responses[0]["headers"])
    assert b"retry-after" in headers


async def test_429_response_includes_retry_after_header() -> None:
    """The Retry-After header value is a positive integer string."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: firestore_client)
    await middleware(_make_scope(tier="basic"), _noop_receive, capture_send)

    assert responses[0]["status"] == 429
    headers = dict(responses[0]["headers"])
    retry_after_value = int(headers[b"retry-after"])
    assert retry_after_value >= 1


async def test_unknown_tier_falls_back_to_basic_limit() -> None:
    """An unrecognised tier string defaults to basic-tier monthly quota."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=RATE_LIMIT_BASIC + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: firestore_client)
    await middleware(_make_scope(tier="enterprise"), _noop_receive, capture_send)

    assert responses[0]["status"] == 429


# ---------------------------------------------------------------------------
# Fail-open (Firestore unavailable) tests
# ---------------------------------------------------------------------------


async def test_firestore_exception_fails_open() -> None:
    """When Firestore raises a GoogleAPICallError the request passes through."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)
    doc_ref.get = AsyncMock(
        side_effect=gcp_exceptions.GoogleAPICallError("firestore down")  # type: ignore[no-untyped-call]
    )

    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)

    with patch("src.middleware.rate_limit.logger") as mock_logger:
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True
    mock_logger.warning.assert_called_once()


async def test_firestore_factory_exception_fails_open() -> None:
    """If the Firestore factory itself raises (e.g. before lifespan), fail-open."""
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
# get_firestore_client tests (src/server.py)
# ---------------------------------------------------------------------------


def test_get_firestore_client_raises_before_lifespan() -> None:
    """get_firestore_client() raises RuntimeError when called outside lifespan."""
    import src.server as server_module
    from src.server import get_firestore_client

    original = server_module._firestore_client
    try:
        server_module._firestore_client = None
        with pytest.raises(RuntimeError, match="not initialized"):
            get_firestore_client()
    finally:
        server_module._firestore_client = original
