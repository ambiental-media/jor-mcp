from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

DEV_ORIGIN = "http://localhost:3000"
PROD_ORIGIN = "https://jormcp.ambiental.media"


def _client() -> TestClient:
    """Return a TestClient instance bound to the Starlette application."""
    from src.server import app

    return TestClient(app, raise_server_exceptions=False)


def _fake_firestore() -> tuple[MagicMock, MagicMock]:
    """Return (db, doc_ref) where db.collection(...).document(...).set is awaitable."""
    doc_ref = MagicMock()
    doc_ref.set = AsyncMock()
    collection = MagicMock()
    collection.document.return_value = doc_ref
    db = MagicMock()
    db.collection.return_value = collection
    return db, doc_ref


# ---------------------------------------------------------------------------
# Router integration (acceptance criterion 1)
# ---------------------------------------------------------------------------


def test_oauth_health_responds_without_auth() -> None:
    """GET /api/oauth/health is reachable without a Firebase token."""
    resp = _client().get("/api/oauth/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "jor-mcp-oauth"}


# ---------------------------------------------------------------------------
# CORS configuration (acceptance criterion 2)
# ---------------------------------------------------------------------------


def test_preflight_allows_dev_origin() -> None:
    """OPTIONS preflight from the dev portal returns the matching ACAO header."""
    resp = _client().options(
        "/api/oauth/approve",
        headers={
            "Origin": DEV_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == DEV_ORIGIN


def test_preflight_allows_prod_origin() -> None:
    """OPTIONS preflight from the production portal returns the matching ACAO header."""
    resp = _client().options(
        "/api/oauth/approve",
        headers={
            "Origin": PROD_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == PROD_ORIGIN


def test_preflight_rejects_unknown_origin() -> None:
    """A non-whitelisted origin must not be echoed back in the ACAO header."""
    resp = _client().options(
        "/api/oauth/approve",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"


def test_simple_request_includes_cors_header() -> None:
    """A GET with an allowed Origin echoes the ACAO header on the response."""
    resp = _client().get("/api/oauth/health", headers={"Origin": DEV_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == DEV_ORIGIN


# ---------------------------------------------------------------------------
# Discovery metadata (Task 2, acceptance criterion 1)
# ---------------------------------------------------------------------------


def test_authorization_server_metadata_returns_server_and_portal_urls() -> None:
    """GET /.well-known/oauth-authorization-server returns valid RFC 8414 metadata."""
    resp = _client().get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    data = resp.json()
    assert data["issuer"]
    assert data["authorization_endpoint"].endswith("/authorize")
    assert data["token_endpoint"].endswith("/api/oauth/token")
    assert data["registration_endpoint"].endswith("/api/oauth/register")
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert data["token_endpoint_auth_methods_supported"] == ["none"]


def test_protected_resource_metadata_points_at_auth_server() -> None:
    """GET /.well-known/oauth-protected-resource returns valid RFC 9728 metadata."""
    resp = _client().get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource"]
    assert isinstance(data["authorization_servers"], list)
    assert data["authorization_servers"]


# ---------------------------------------------------------------------------
# Dynamic Client Registration (Task 2, acceptance criteria 2 & 3)
# ---------------------------------------------------------------------------


@patch("src.server.get_firestore_client")
def test_register_forces_public_client_and_normalizes_loopback(
    mock_get_db: MagicMock,
) -> None:
    """POST /api/oauth/register registers a public client and normalizes
    loopback URIs in Firestore."""
    db, doc_ref = _fake_firestore()
    mock_get_db.return_value = db

    resp = _client().post(
        "/api/oauth/register",
        json={
            "client_name": "Claude Desktop",
            "redirect_uris": [
                "http://127.0.0.1:54321/callback",
                "https://example.com/cb",
            ],
            "token_endpoint_auth_method": "client_secret_basic",
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["token_endpoint_auth_method"] == "none"
    assert data["redirect_uris"] == [
        "http://localhost:54321/callback",
        "https://example.com/cb",
    ]
    assert data["client_id"]

    db.collection.assert_called_once_with("oauth_clients")
    db.collection.return_value.document.assert_called_once_with(data["client_id"])
    doc_ref.set.assert_awaited_once()
    saved = doc_ref.set.call_args.args[0]
    assert saved["client_id"] == data["client_id"]
    assert saved["token_endpoint_auth_method"] == "none"
    assert saved["redirect_uris"] == [
        "http://localhost:54321/callback",
        "https://example.com/cb",
    ]


@patch("src.server.get_firestore_client")
def test_register_rejects_missing_redirect_uris(mock_get_db: MagicMock) -> None:
    """POST /api/oauth/register rejects payload with a 400 error when redirect_uris is missing."""
    resp = _client().post("/api/oauth/register", json={"client_name": "X"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client_metadata"
    mock_get_db.assert_not_called()


def test_register_rejects_non_json_body() -> None:
    """POST /api/oauth/register rejects unparseable non-JSON request bodies with a 400 error."""
    resp = _client().post(
        "/api/oauth/register",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"
