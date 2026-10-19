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


def _make_firestore_mock(*, count: int = 1, exists: bool = True) -> tuple[MagicMock, MagicMock]:
    """Build a Firestore client mock whose stored token counter resolves to *count*.

    ``count`` is the number of tokens already charged to the current weekly
    window, i.e. what the middleware reads *before* serving the request.
    """
    firestore_client = MagicMock()
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.get.return_value = count

    doc_ref.set = AsyncMock(return_value=None)
    doc_ref.get = AsyncMock(return_value=snapshot)

    collection_ref = MagicMock()
    collection_ref.document.return_value = doc_ref
    firestore_client.collection.return_value = collection_ref

    return firestore_client, doc_ref


def _responding_app(body: bytes) -> Any:
    """Return an inner ASGI app that answers with *body*, so the meter sees payload."""

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": body, "more_body": False})

    return inner_app


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
    with patch.dict("src.middleware.rate_limit.TIER_QUOTAS", {"basic": 500}):
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


async def test_uses_weekly_document_id() -> None:
    """Document id follows the {uid}_YYYY-Www fixed weekly window convention."""
    from datetime import UTC, datetime

    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=1)
    fixed_now = datetime(2026, 5, 20, 12, 30, tzinfo=UTC)  # ISO week 21 of 2026

    middleware = RateLimitMiddleware(AsyncMock(), lambda: firestore_client)

    with patch("src.middleware.rate_limit.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        await middleware(_make_scope(uid="abc-123"), _noop_receive, AsyncMock())

    firestore_client.collection.return_value.document.assert_called_with("abc-123_2026-W21")


async def test_charges_measured_tokens_with_atomic_increment() -> None:
    """Usage is recorded after the response, with firestore.Increment."""
    from google.cloud import firestore

    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)
    middleware = RateLimitMiddleware(_responding_app(b"x" * 400), lambda: firestore_client)

    await middleware(_make_scope(), _noop_receive, AsyncMock())

    doc_ref.set.assert_awaited_once()
    payload = doc_ref.set.call_args.args[0]
    assert isinstance(payload["tokens"], type(firestore.Increment(1)))
    assert doc_ref.set.call_args.kwargs["merge"] is True


async def test_quota_is_checked_before_the_request_runs() -> None:
    """The window counter is read before the inner app is reached."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=10)
    order: list[str] = []

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        order.append("app")

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.get.return_value = 10

    async def recording_get(*args: Any, **kwargs: Any) -> MagicMock:
        order.append("read")
        return snapshot

    doc_ref.get = AsyncMock(side_effect=recording_get)

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert order == ["read", "app"]


async def test_window_without_document_starts_at_zero() -> None:
    """The first request of a window reads a missing document as zero usage."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(exists=False)
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_no_usage_means_no_write() -> None:
    """A request that exchanges no payload does not touch the counter."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)
    middleware = RateLimitMiddleware(AsyncMock(), lambda: firestore_client)

    await middleware(_make_scope(), _noop_receive, AsyncMock())

    doc_ref.set.assert_not_awaited()


async def test_charges_both_request_and_response_payloads() -> None:
    """Tokens billed cover what the client sent and what the server answered."""
    from google.cloud import firestore

    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)

    async def receive_with_body() -> dict[str, Any]:
        return {"type": "http.request", "body": b"q" * 200, "more_body": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"r" * 600, "more_body": False})

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware(_make_scope(), receive_with_body, AsyncMock())

    charged = doc_ref.set.call_args.args[0]["tokens"]
    # 200 request chars + 600 response chars, at four characters per token.
    assert charged == firestore.Increment(200)


async def test_streamed_response_chunks_are_all_counted() -> None:
    """A chunked response is charged for every chunk, not just the first."""
    from google.cloud import firestore

    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)

    async def streaming_app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        for _ in range(3):
            await send({"type": "http.response.body", "body": b"z" * 400, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    middleware = RateLimitMiddleware(streaming_app, lambda: firestore_client)
    await middleware(_make_scope(), _noop_receive, AsyncMock())

    charged = doc_ref.set.call_args.args[0]["tokens"]
    assert charged == firestore.Increment(300)


async def test_accounting_failure_does_not_break_the_response() -> None:
    """A Firestore error while charging usage is logged, not raised."""
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, doc_ref = _make_firestore_mock(count=1)
    doc_ref.set = AsyncMock(
        side_effect=gcp_exceptions.DeadlineExceeded("timeout")  # type: ignore[no-untyped-call]
    )

    middleware = RateLimitMiddleware(_responding_app(b"y" * 400), lambda: firestore_client)

    await middleware(_make_scope(), _noop_receive, AsyncMock())

    doc_ref.set.assert_awaited_once()


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


async def test_pro_tier_gets_the_larger_quota() -> None:
    """A 'pro' user is still served past the basic quota, up to the pro one."""
    from src.config import RATE_LIMIT_BASIC
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=RATE_LIMIT_BASIC + 1)
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    middleware = RateLimitMiddleware(inner_app, lambda: firestore_client)
    await middleware(_make_scope(tier="pro"), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_pro_tier_over_its_own_quota_returns_429() -> None:
    """The pro quota is enforced too — it is a larger limit, not an exemption."""
    from src.config import RATE_LIMIT_PRO
    from src.middleware.rate_limit import RateLimitMiddleware

    firestore_client, _doc_ref = _make_firestore_mock(count=RATE_LIMIT_PRO + 1)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    middleware = RateLimitMiddleware(MagicMock(), lambda: firestore_client)
    await middleware(_make_scope(tier="pro"), _noop_receive, capture_send)

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


class TestWeekKey:
    def test_formats_the_iso_week_with_two_digits(self) -> None:
        from datetime import UTC, datetime

        from src.middleware.rate_limit import _week_key

        assert _week_key(datetime(2026, 1, 8, tzinfo=UTC)) == "2026-W02"

    def test_uses_the_iso_year_across_a_year_boundary(self) -> None:
        """2027-01-01 is a Friday, so ISO-8601 counts it as week 53 of 2026."""
        from datetime import UTC, datetime

        from src.middleware.rate_limit import _week_key

        assert _week_key(datetime(2027, 1, 1, tzinfo=UTC)) == "2026-W53"


class TestSecondsUntilNextWeek:
    def test_counts_down_to_monday_midnight(self) -> None:
        from datetime import UTC, datetime

        from src.middleware.rate_limit import _seconds_until_next_week

        # Sunday 23:59:30 UTC -> 30 seconds left in the window.
        now = datetime(2026, 10, 11, 23, 59, 30, tzinfo=UTC)
        assert _seconds_until_next_week(now) == 30

    def test_a_full_week_is_left_right_after_a_reset(self) -> None:
        from datetime import UTC, datetime

        from src.middleware.rate_limit import _seconds_until_next_week

        # Monday 00:00 UTC -> the whole week remains.
        now = datetime(2026, 10, 5, 0, 0, 0, tzinfo=UTC)
        assert _seconds_until_next_week(now) == 7 * 24 * 60 * 60
