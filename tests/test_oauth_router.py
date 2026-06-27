from starlette.testclient import TestClient

DEV_ORIGIN = "http://localhost:3000"
PROD_ORIGIN = "https://jor-mcp.ambiental.media"


def _client() -> TestClient:
    from src.server import app

    return TestClient(app, raise_server_exceptions=False)


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
