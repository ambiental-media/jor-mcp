from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from src.server import app

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# HTTP-level tests via TestClient
# ---------------------------------------------------------------------------


def test_health_bypasses_auth(client: TestClient) -> None:
    """GET /health must succeed without any Authorization header."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_missing_authorization_header_returns_401(client: TestClient) -> None:
    resp = client.get("/mcp/")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Unauthorized"}


def test_wrong_auth_scheme_returns_401(client: TestClient) -> None:
    resp = client.get("/mcp/", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 401


def test_bearer_prefix_only_returns_401(client: TestClient) -> None:
    """'Bearer ' with no token value should be rejected."""
    resp = client.get("/mcp/", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_valid_token_passes_to_application(client: TestClient) -> None:
    decoded: dict[str, Any] = {"uid": "user-123", "tier": "pro"}
    with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer valid.jwt.token"})
    assert resp.status_code != 401


def test_firebase_error_returns_401(client: TestClient) -> None:
    import firebase_admin.exceptions

    err = firebase_admin.exceptions.FirebaseError(
        code="INVALID_ARGUMENT", message="bad token"
    )
    with patch("firebase_admin.auth.verify_id_token", side_effect=err):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer bad.token"})
    assert resp.status_code == 401


def test_value_error_on_token_returns_401(client: TestClient) -> None:
    with patch(
        "firebase_admin.auth.verify_id_token", side_effect=ValueError("malformed")
    ):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer malformed"})
    assert resp.status_code == 401


def test_expired_token_returns_401(client: TestClient) -> None:
    from firebase_admin.auth import ExpiredIdTokenError

    with patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=ExpiredIdTokenError("Token expired", None),
    ):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer expired.token"})
    assert resp.status_code == 401


def test_invalid_token_returns_401(client: TestClient) -> None:
    from firebase_admin.auth import InvalidIdTokenError

    with patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=InvalidIdTokenError("Token invalid"),
    ):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer invalid.token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Direct async unit tests — inspect scope["user"] via a spy ASGI app
# ---------------------------------------------------------------------------


async def test_user_scope_injection_with_tier() -> None:
    """scope['user'] receives uid and tier from the decoded token."""
    captured: dict[str, Any] = {}

    async def spy_app(scope: Any, receive: Any, send: Any) -> None:
        captured["user"] = scope.get("user")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    from src.middleware.auth import AuthMiddleware

    middleware = AuthMiddleware(spy_app)
    scope: dict[str, Any] = {
        "type": "http",
        "path": "/test",
        "headers": [(b"authorization", b"Bearer valid.token")],
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Any) -> None:
        pass

    decoded: dict[str, Any] = {"uid": "uid-abc", "tier": "pro"}
    with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
        await middleware(scope, receive, send)

    assert captured["user"] == {"uid": "uid-abc", "tier": "pro"}


async def test_user_scope_defaults_tier_to_basic() -> None:
    """When token has no 'tier' claim, scope['user']['tier'] defaults to 'basic'."""
    captured: dict[str, Any] = {}

    async def spy_app(scope: Any, receive: Any, send: Any) -> None:
        captured["user"] = scope.get("user")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    from src.middleware.auth import AuthMiddleware

    middleware = AuthMiddleware(spy_app)
    scope: dict[str, Any] = {
        "type": "http",
        "path": "/test",
        "headers": [(b"authorization", b"Bearer valid.token")],
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Any) -> None:
        pass

    decoded: dict[str, Any] = {"uid": "uid-xyz"}  # no tier claim
    with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
        await middleware(scope, receive, send)

    assert captured["user"] == {"uid": "uid-xyz", "tier": "basic"}


async def test_non_http_scope_passes_through_without_auth() -> None:
    """Lifespan and other non-HTTP scopes bypass authentication entirely."""
    called = {"app": False}

    async def inner_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

    from src.middleware.auth import AuthMiddleware

    middleware = AuthMiddleware(inner_app)

    async def receive() -> dict[str, Any]:
        return {}

    async def send(message: Any) -> None:
        pass

    await middleware({"type": "lifespan"}, receive, send)
    assert called["app"] is True


# ---------------------------------------------------------------------------
# __init__ branch coverage
# ---------------------------------------------------------------------------


def test_auth_middleware_init_initializes_app_when_not_present() -> None:
    """__init__ calls initialize_app() when no Firebase app exists yet."""
    from src.middleware.auth import AuthMiddleware

    with patch("firebase_admin.get_app", side_effect=ValueError("No app")), patch(
        "firebase_admin.initialize_app"
    ) as mock_init:
        AuthMiddleware(MagicMock())
        mock_init.assert_called_once()


def test_auth_middleware_init_skips_init_when_app_exists() -> None:
    """__init__ does NOT call initialize_app() when an app is already registered."""
    from src.middleware.auth import AuthMiddleware

    with patch("firebase_admin.get_app", return_value=MagicMock()), patch(
        "firebase_admin.initialize_app"
    ) as mock_init:
        AuthMiddleware(MagicMock())
        mock_init.assert_not_called()
