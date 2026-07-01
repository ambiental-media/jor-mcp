from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

DEV_ORIGIN = "http://localhost:3000"
PROD_ORIGIN = "https://jormcp.ambiental.media"


def _client() -> TestClient:
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


def _fake_firestore_for_approve(
    redirect_uris: list[str],
    *,
    client_exists: bool = True,
    user_allowed: bool = True,
    user_status: str = "active",
) -> tuple[MagicMock, MagicMock]:
    """Return (db, codes_doc) wiring the client, allow-list and oauth_codes access."""
    snapshot = MagicMock()
    snapshot.exists = client_exists
    snapshot.get.return_value = redirect_uris
    clients_doc = MagicMock()
    clients_doc.get = AsyncMock(return_value=snapshot)
    clients_collection = MagicMock()
    clients_collection.document.return_value = clients_doc

    allowed_snapshot = MagicMock()
    allowed_snapshot.exists = user_allowed
    allowed_snapshot.to_dict.return_value = {"status": user_status}
    allowed_doc = MagicMock()
    allowed_doc.get = AsyncMock(return_value=allowed_snapshot)
    allowed_collection = MagicMock()
    allowed_collection.document.return_value = allowed_doc

    codes_doc = MagicMock()
    codes_doc.set = AsyncMock()
    codes_collection = MagicMock()
    codes_collection.document.return_value = codes_doc

    collections = {
        "oauth_clients": clients_collection,
        "allowed_users": allowed_collection,
        "oauth_codes": codes_collection,
    }
    db = MagicMock()
    db.collection.side_effect = lambda name: collections[name]
    return db, codes_doc


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
    resp = _client().post("/api/oauth/register", json={"client_name": "X"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client_metadata"
    mock_get_db.assert_not_called()


def test_register_rejects_non_json_body() -> None:
    resp = _client().post(
        "/api/oauth/register",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


# ---------------------------------------------------------------------------
# Consent approval (Task 3)
# ---------------------------------------------------------------------------


def test_approve_without_token_returns_401() -> None:
    """Acceptance criterion 1: no Firebase JWT -> 401."""
    resp = _client().post(
        "/api/oauth/approve",
        json={"client_id": "c", "code_challenge": "ch"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


@patch("src.api.oauth.auth.verify_id_token", side_effect=ValueError("bad token"))
def test_approve_invalid_token_returns_401(_mock_verify: MagicMock) -> None:
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer bad"},
        json={"client_id": "c", "code_challenge": "ch"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "invalid_token"


@patch("src.api.oauth.auth.verify_id_token", return_value={"uid": "u"})
def test_approve_rejects_non_json_body(_mock_verify: MagicMock) -> None:
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok", "Content-Type": "application/json"},
        content="not-json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


@patch("src.api.oauth.auth.verify_id_token", return_value={"uid": "u"})
def test_approve_rejects_missing_fields(_mock_verify: MagicMock) -> None:
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={"client_id": "c"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


@patch("src.api.oauth.auth.verify_id_token", return_value={"uid": "u"})
def test_approve_rejects_non_s256_method(_mock_verify: MagicMock) -> None:
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "c",
            "code_challenge": "ch",
            "code_challenge_method": "plain",
            "redirect_uri": "http://localhost:1/cb",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


@patch("src.server.get_firestore_client")
@patch("src.api.oauth.auth.verify_id_token", return_value={"uid": "u"})
def test_approve_unknown_client_returns_400(
    _mock_verify: MagicMock, mock_get_db: MagicMock
) -> None:
    """Acceptance criterion 2: non-existent client_id -> 400."""
    db, _ = _fake_firestore_for_approve([], client_exists=False)
    mock_get_db.return_value = db
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "missing",
            "code_challenge": "ch",
            "redirect_uri": "http://localhost:1/cb",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_client"


@patch("src.server.get_firestore_client")
@patch("src.api.oauth.auth.verify_id_token", return_value={"uid": "u"})
def test_approve_unregistered_redirect_returns_400(
    _mock_verify: MagicMock, mock_get_db: MagicMock
) -> None:
    db, _ = _fake_firestore_for_approve(["http://localhost:54321/callback"])
    mock_get_db.return_value = db
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "c",
            "code_challenge": "ch",
            "redirect_uri": "http://evil.example.com/cb",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


@patch("src.server.get_firestore_client")
@patch(
    "src.api.oauth.auth.verify_id_token",
    return_value={"uid": "user-123", "email": "user@ambiental.media"},
)
def test_approve_issues_code_and_persists_pkce_state(
    _mock_verify: MagicMock, mock_get_db: MagicMock
) -> None:
    """Acceptance criterion 3: valid request creates oauth_codes doc and returns code."""
    db, codes_doc = _fake_firestore_for_approve(["http://localhost:54321/callback"])
    mock_get_db.return_value = db

    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "client-abc",
            "code_challenge": "challenge-xyz",
            "redirect_uri": "http://127.0.0.1:54321/callback",
            "state": "st-1",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    code = data["authorization_code"]
    assert code
    assert data["redirect_uri"].startswith("http://localhost:54321/callback?")
    assert f"code={code}" in data["redirect_uri"]
    assert "state=st-1" in data["redirect_uri"]

    codes_doc.set.assert_awaited_once()
    saved = codes_doc.set.call_args.args[0]
    assert saved["code"] == code
    assert saved["uid"] == "user-123"
    assert saved["client_id"] == "client-abc"
    assert saved["code_challenge"] == "challenge-xyz"
    assert saved["redirect_uri"] == "http://localhost:54321/callback"


@patch("src.server.get_firestore_client")
@patch(
    "src.api.oauth.auth.verify_id_token",
    return_value={"uid": "u", "email": "user@ambiental.media"},
)
def test_approve_falls_back_to_registered_redirect(
    _mock_verify: MagicMock, mock_get_db: MagicMock
) -> None:
    db, _ = _fake_firestore_for_approve(["http://localhost:9000/cb"])
    mock_get_db.return_value = db
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={"client_id": "c", "code_challenge": "ch"},
    )
    assert resp.status_code == 200
    assert resp.json()["redirect_uri"].startswith("http://localhost:9000/cb?code=")


# ---------------------------------------------------------------------------
# Consent allow-list (Task 3, updated: 403 for non-whitelisted users)
# ---------------------------------------------------------------------------


@patch("src.server.get_firestore_client")
@patch(
    "src.api.oauth.auth.verify_id_token",
    return_value={"uid": "u", "email": "blocked@gmail.com"},
)
def test_approve_rejects_user_not_in_whitelist(
    _mock_verify: MagicMock, mock_get_db: MagicMock
) -> None:
    """Acceptance criterion 4: valid JWT but email not whitelisted -> 403."""
    db, codes_doc = _fake_firestore_for_approve(["http://localhost:1/cb"], user_allowed=False)
    mock_get_db.return_value = db
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "c",
            "code_challenge": "ch",
            "redirect_uri": "http://localhost:1/cb",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "access_denied"
    codes_doc.set.assert_not_awaited()


@patch("src.server.get_firestore_client")
@patch(
    "src.api.oauth.auth.verify_id_token",
    return_value={"uid": "u", "email": "inactive@ambiental.media"},
)
def test_approve_rejects_inactive_user(_mock_verify: MagicMock, mock_get_db: MagicMock) -> None:
    """A whitelisted email whose status is not 'active' is rejected with 403."""
    db, _ = _fake_firestore_for_approve(["http://localhost:1/cb"], user_status="disabled")
    mock_get_db.return_value = db
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "c",
            "code_challenge": "ch",
            "redirect_uri": "http://localhost:1/cb",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "access_denied"


@patch("src.server.get_firestore_client")
@patch("src.api.oauth.auth.verify_id_token", return_value={"uid": "u"})
def test_approve_rejects_token_without_email(
    _mock_verify: MagicMock, mock_get_db: MagicMock
) -> None:
    """A token carrying no email claim cannot be whitelisted -> 403."""
    db, _ = _fake_firestore_for_approve(["http://localhost:1/cb"])
    mock_get_db.return_value = db
    resp = _client().post(
        "/api/oauth/approve",
        headers={"Authorization": "Bearer ok"},
        json={
            "client_id": "c",
            "code_challenge": "ch",
            "redirect_uri": "http://localhost:1/cb",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "access_denied"
