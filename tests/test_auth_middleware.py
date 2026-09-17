from typing import Any
from unittest.mock import patch

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


def test_401_advertises_resource_metadata(client: TestClient) -> None:
    """The 401 must carry a WWW-Authenticate header pointing at the resource metadata.

    This is the discovery trigger that makes MCP clients (e.g. Claude Desktop)
    start the OAuth flow instead of giving up.
    """
    resp = client.get("/mcp/")
    header = resp.headers["www-authenticate"]
    assert header.startswith("Bearer ")
    assert 'resource_metadata="' in header
    assert header.endswith('/.well-known/oauth-protected-resource"')


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

    err = firebase_admin.exceptions.FirebaseError(code="INVALID_ARGUMENT", message="bad token")
    with patch("firebase_admin.auth.verify_id_token", side_effect=err):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer bad.token"})
    assert resp.status_code == 401


def test_value_error_on_token_returns_401(client: TestClient) -> None:
    with patch("firebase_admin.auth.verify_id_token", side_effect=ValueError("malformed")):
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


async def test_token_without_tier_claim_is_rejected() -> None:
    """A user who was never assigned a role never reaches the application."""
    called = {"app": False}
    responses: list[dict[str, Any]] = []

    async def spy_app(scope: Any, receive: Any, send: Any) -> None:
        called["app"] = True

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
        responses.append(dict(message))

    decoded: dict[str, Any] = {"uid": "uid-xyz"}  # no tier claim
    with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
        await middleware(scope, receive, send)

    assert called["app"] is False
    assert responses[0]["status"] == 403


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


def test_token_without_tier_returns_403(client: TestClient) -> None:
    """A valid token with no role claim is authenticated but not authorized."""
    with patch("firebase_admin.auth.verify_id_token", return_value={"uid": "user-123"}):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer valid.jwt.token"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_403_does_not_advertise_resource_metadata(client: TestClient) -> None:
    """The 403 must not trigger an OAuth re-authentication loop in MCP clients."""
    with patch("firebase_admin.auth.verify_id_token", return_value={"uid": "user-123"}):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer valid.jwt.token"})
    assert "www-authenticate" not in resp.headers


def test_unknown_tier_returns_403(client: TestClient) -> None:
    """A role that is not in TIER_QUOTAS is rejected instead of downgraded."""
    decoded: dict[str, Any] = {"uid": "user-123", "tier": "enterprise"}
    with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer valid.jwt.token"})
    assert resp.status_code == 403


def test_validation_error_on_token_returns_401(client: TestClient) -> None:
    """A Pydantic ValidationError during token validation returns 401."""
    # verify_id_token returns a dict missing the required 'uid' field,
    # which causes DecodedToken.model_validate() to raise ValidationError.
    with patch("firebase_admin.auth.verify_id_token", return_value={"email": "test@example.com"}):
        resp = client.get("/mcp/", headers={"Authorization": "Bearer valid.jwt.token"})
    assert resp.status_code == 401
