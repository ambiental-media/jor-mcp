"""Unit tests for IPRateLimitMiddleware.

Uses the "Spy App" pattern to assert whether a request reaches the inner
application. The Firestore client is always mocked so no real Firestore access
is required.
"""

from collections.abc import MutableMapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as gcp_exceptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WINDOW = (1700000000, 1700000060)
"""Deterministic (start, end) epoch pair used to assert document ids."""


def _fixed_window() -> Any:
    """Pin the fixed-window boundaries so document ids are predictable."""
    return patch("src.middleware.ip_rate_limit._window_bounds", return_value=_WINDOW)


def _make_scope(
    path: str = "/api/oauth/register",
    client: tuple[str, int] | None = ("203.0.113.7", 54321),
    forwarded_for: str | None = None,
) -> dict[str, Any]:
    """Build a minimal ASGI HTTP scope targeting an unauthenticated route."""
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"X-Forwarded-For", forwarded_for.encode()))
    return {"type": "http", "path": path, "headers": headers, "client": client}


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_firestore_mock(*, count: int = 1) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build a Firestore client mock whose post-increment count resolves to *count*."""
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

    return firestore_client, collection_ref, doc_ref


def _spy_app(state: dict[str, bool]) -> Any:
    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        state["app"] = True

    return inner_app


# ---------------------------------------------------------------------------
# Bypass tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/health", "/mcp/", "/", "/api/other"])
async def test_authenticated_and_health_paths_bypass_ip_limit(path: str) -> None:
    """Only auth-exempt OAuth paths are metered; everything else passes through."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, doc_ref = _make_firestore_mock()
    called = {"app": False}

    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)
    await middleware(_make_scope(path=path), _noop_receive, AsyncMock())

    assert called["app"] is True
    doc_ref.set.assert_not_called()


async def test_non_http_scope_passes_through() -> None:
    """Lifespan and other non-HTTP scopes bypass IP rate limiting."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, doc_ref = _make_firestore_mock()
    called = {"app": False}

    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)
    await middleware({"type": "lifespan"}, _noop_receive, AsyncMock())

    assert called["app"] is True
    doc_ref.set.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        "/api/oauth/register",
        "/api/oauth/token",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource",
    ],
)
async def test_unauthenticated_paths_are_metered(path: str) -> None:
    """Discovery and OAuth proxy routes increment the per-IP counter."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, doc_ref = _make_firestore_mock(count=1)
    called = {"app": False}

    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)
    await middleware(_make_scope(path=path), _noop_receive, AsyncMock())

    assert called["app"] is True
    doc_ref.set.assert_awaited_once()


# ---------------------------------------------------------------------------
# Client IP extraction tests
# ---------------------------------------------------------------------------


async def test_uses_asgi_client_when_no_forwarded_header() -> None:
    """Without X-Forwarded-For the ASGI client peer address is used."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, collection_ref, _doc_ref = _make_firestore_mock(count=1)

    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)
    with _fixed_window():
        await middleware(_make_scope(client=("198.51.100.4", 1234)), _noop_receive, AsyncMock())

    collection_ref.document.assert_called_once_with("198-51-100-4_1700000000")


async def test_forwarded_for_is_read_from_the_right() -> None:
    """With one trusted proxy, the second-to-last XFF entry wins over spoofed ones."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, collection_ref, _doc_ref = _make_firestore_mock(count=1)

    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)
    with (
        patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_TRUSTED_PROXIES", 1),
        _fixed_window(),
    ):
        await middleware(
            _make_scope(forwarded_for="1.2.3.4, 198.51.100.9, 10.0.0.1"),
            _noop_receive,
            AsyncMock(),
        )

    collection_ref.document.assert_called_once_with("198-51-100-9_1700000000")


async def test_forwarded_for_without_proxies_uses_last_entry() -> None:
    """With zero trusted proxies the right-most XFF entry is the client."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, collection_ref, _doc_ref = _make_firestore_mock(count=1)

    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)
    with (
        patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_TRUSTED_PROXIES", 0),
        _fixed_window(),
    ):
        await middleware(
            _make_scope(forwarded_for="1.2.3.4, 198.51.100.9"), _noop_receive, AsyncMock()
        )

    collection_ref.document.assert_called_once_with("198-51-100-9_1700000000")


async def test_malformed_forwarded_for_falls_back_to_peer() -> None:
    """A garbage X-Forwarded-For value never reaches the Firestore document id."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, collection_ref, _doc_ref = _make_firestore_mock(count=1)

    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)
    with (
        patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_TRUSTED_PROXIES", 0),
        _fixed_window(),
    ):
        await middleware(
            _make_scope(forwarded_for="../../evil/path", client=("198.51.100.4", 1234)),
            _noop_receive,
            AsyncMock(),
        )

    collection_ref.document.assert_called_once_with("198-51-100-4_1700000000")


async def test_missing_client_falls_back_to_unknown_bucket() -> None:
    """When neither header nor peer address is usable, a shared bucket is used."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, collection_ref, _doc_ref = _make_firestore_mock(count=1)

    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)
    with _fixed_window():
        await middleware(_make_scope(client=None), _noop_receive, AsyncMock())

    collection_ref.document.assert_called_once_with("unknown_1700000000")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("203.0.113.7:443", "203.0.113.7"),
        ("[2001:db8::1]:8443", "2001:db8::1"),
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
        ("  203.0.113.7  ", "203.0.113.7"),
        ("not-an-ip", None),
        ("", None),
    ],
)
def test_normalize_ip(raw: str, expected: str | None) -> None:
    """IPv4/IPv6 forms with optional ports normalise; junk returns None."""
    from src.middleware.ip_rate_limit import _normalize_ip

    assert _normalize_ip(raw) == expected


async def test_ipv6_document_id_is_sanitized() -> None:
    """IPv6 colons are replaced so the document id stays readable."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, collection_ref, _doc_ref = _make_firestore_mock(count=1)

    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)
    with _fixed_window():
        await middleware(_make_scope(client=("2001:db8::1", 443)), _noop_receive, AsyncMock())

    collection_ref.document.assert_called_once_with("2001-db8--1_1700000000")


# ---------------------------------------------------------------------------
# Fixed window behaviour
# ---------------------------------------------------------------------------


def test_window_bounds_are_epoch_aligned() -> None:
    """Window boundaries are multiples of the configured window length."""
    from datetime import UTC, datetime

    from src.middleware.ip_rate_limit import _window_bounds

    now = datetime.fromtimestamp(1700000037, UTC)
    with patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_WINDOW_SECONDS", 60):
        start, end = _window_bounds(now)

    assert start == 1699999980
    assert end == 1700000040
    assert start % 60 == 0


async def test_uses_atomic_increment_for_count() -> None:
    """The per-IP check increments the counter with firestore.Increment(1)."""
    from google.cloud import firestore

    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, doc_ref = _make_firestore_mock(count=1)
    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)

    await middleware(_make_scope(), _noop_receive, AsyncMock())

    doc_ref.set.assert_awaited_once()
    payload = doc_ref.set.call_args.args[0]
    assert isinstance(payload["count"], type(firestore.Increment(1)))
    assert doc_ref.set.call_args.kwargs["merge"] is True
    doc_ref.get.assert_awaited_once()


async def test_document_carries_expiry_for_ttl_cleanup() -> None:
    """Each window document stores expires_at so a Firestore TTL policy can prune it."""
    from datetime import datetime

    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, doc_ref = _make_firestore_mock(count=1)
    middleware = IPRateLimitMiddleware(AsyncMock(), lambda: firestore_client)

    with _fixed_window():
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    payload = doc_ref.set.call_args.args[0]
    assert isinstance(payload["expires_at"], datetime)
    assert int(payload["expires_at"].timestamp()) == 1700000060


async def test_request_within_limit_is_allowed() -> None:
    """A request under the per-IP limit reaches the inner application."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, _doc_ref = _make_firestore_mock(count=10)
    called = {"app": False}

    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)
    with patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_REQUESTS", 60):
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_request_at_limit_is_allowed() -> None:
    """The Nth request of the window is still allowed (rejection starts at N+1)."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, _doc_ref = _make_firestore_mock(count=60)
    called = {"app": False}

    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)
    with patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_REQUESTS", 60):
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True


async def test_request_over_limit_returns_429_with_retry_after() -> None:
    """Exceeding the per-IP window returns 429 with a positive Retry-After."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, _doc_ref = _make_firestore_mock(count=61)

    responses: list[dict[str, Any]] = []

    async def capture_send(message: MutableMapping[str, Any]) -> None:
        responses.append(dict(message))

    called = {"app": False}

    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)
    with patch("src.middleware.ip_rate_limit.IP_RATE_LIMIT_REQUESTS", 60):
        await middleware(_make_scope(), _noop_receive, capture_send)

    assert called["app"] is False
    assert responses[0]["status"] == 429
    headers = dict(responses[0]["headers"])
    retry_after = int(headers[b"retry-after"])
    assert 1 <= retry_after <= 60


# ---------------------------------------------------------------------------
# Fail-open (Firestore unavailable) tests
# ---------------------------------------------------------------------------


async def test_firestore_exception_fails_open() -> None:
    """When Firestore raises a GoogleAPICallError the request passes through."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    firestore_client, _collection, doc_ref = _make_firestore_mock(count=1)
    doc_ref.set = AsyncMock(
        side_effect=gcp_exceptions.GoogleAPICallError("firestore down")  # type: ignore[no-untyped-call]
    )

    called = {"app": False}
    middleware = IPRateLimitMiddleware(_spy_app(called), lambda: firestore_client)

    with patch("src.middleware.ip_rate_limit.logger") as mock_logger:
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True
    mock_logger.warning.assert_called_once()


async def test_firestore_factory_exception_fails_open() -> None:
    """If the Firestore factory itself raises (e.g. before lifespan), fail-open."""
    from src.middleware.ip_rate_limit import IPRateLimitMiddleware

    def broken_factory() -> Any:
        raise RuntimeError("not initialised")

    called = {"app": False}
    middleware = IPRateLimitMiddleware(_spy_app(called), broken_factory)

    with patch("src.middleware.ip_rate_limit.logger") as mock_logger:
        await middleware(_make_scope(), _noop_receive, AsyncMock())

    assert called["app"] is True
    mock_logger.warning.assert_called_once()
