from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient


def test_health_endpoint() -> None:
    from src.server import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "jor-mcp"}


# ---------------------------------------------------------------------------
# server_lifespan branch coverage
# ---------------------------------------------------------------------------


async def test_server_lifespan_initializes_firebase_when_not_present() -> None:
    """server_lifespan calls initialize_app() when no Firebase app exists yet."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    with (
        patch("firebase_admin.get_app", side_effect=ValueError("No app")),
        patch("firebase_admin.initialize_app") as mock_init,
        patch("src.server._mcp_http_app") as mock_mcp_app,
    ):
        mock_mcp_app.lifespan = fake_mcp_lifespan
        async with server_lifespan(MagicMock()):
            pass

    mock_init.assert_called_once()


async def test_server_lifespan_skips_init_when_firebase_already_present() -> None:
    """server_lifespan does NOT call initialize_app() when Firebase is already initialized."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    with (
        patch("firebase_admin.get_app", return_value=MagicMock()),
        patch("firebase_admin.initialize_app") as mock_init,
        patch("src.server._mcp_http_app") as mock_mcp_app,
    ):
        mock_mcp_app.lifespan = fake_mcp_lifespan
        async with server_lifespan(MagicMock()):
            pass

    mock_init.assert_not_called()
