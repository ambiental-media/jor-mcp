from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient


def _make_fake_firestore() -> MagicMock:
    """Return a MagicMock that satisfies the Firestore async interface."""
    fake_firestore = MagicMock()
    fake_firestore.close = AsyncMock()
    return fake_firestore


@patch("src.server.setup_telemetry")
def test_health_endpoint(_mock_setup: MagicMock) -> None:
    from src.server import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "jor-mcp"}


# ---------------------------------------------------------------------------
# server_lifespan branch coverage
# ---------------------------------------------------------------------------


@patch("src.server.setup_telemetry")
@patch("firebase_admin.get_app", side_effect=ValueError("No app"))
@patch("firebase_admin.initialize_app")
@patch("src.server._mcp_http_app")
@patch("src.server.FirestoreAsyncClient")
@patch("httpx.AsyncClient")
async def test_server_lifespan_initializes_firebase_when_not_present(
    mock_http_client_cls: MagicMock,
    mock_firestore_cls: MagicMock,
    mock_mcp_app: MagicMock,
    mock_init: MagicMock,
    _mock_get_app: MagicMock,
    _mock_setup: MagicMock,
) -> None:
    """server_lifespan calls initialize_app() when no Firebase app exists yet."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    fake_firestore = _make_fake_firestore()
    fake_http_client = AsyncMock()
    mock_firestore_cls.return_value = fake_firestore
    mock_http_client_cls.return_value = fake_http_client
    mock_mcp_app.lifespan = fake_mcp_lifespan

    async with server_lifespan(MagicMock()):
        pass

    mock_init.assert_called_once()
    fake_http_client.aclose.assert_awaited_once()
    fake_firestore.close.assert_awaited_once()
    _mock_setup.assert_called_once()


@patch("src.server.setup_telemetry")
@patch("firebase_admin.get_app")
@patch("firebase_admin.initialize_app")
@patch("src.server._mcp_http_app")
@patch("src.server.FirestoreAsyncClient")
@patch("httpx.AsyncClient")
async def test_server_lifespan_skips_init_when_firebase_already_present(
    mock_http_client_cls: MagicMock,
    mock_firestore_cls: MagicMock,
    mock_mcp_app: MagicMock,
    mock_init: MagicMock,
    _mock_get_app: MagicMock,
    _mock_setup: MagicMock,
) -> None:
    """server_lifespan does NOT call initialize_app() when Firebase is already initialized."""
    from src.server import server_lifespan

    @asynccontextmanager
    async def fake_mcp_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    fake_firestore = _make_fake_firestore()
    fake_http_client = AsyncMock()
    mock_firestore_cls.return_value = fake_firestore
    mock_http_client_cls.return_value = fake_http_client
    mock_mcp_app.lifespan = fake_mcp_lifespan

    async with server_lifespan(MagicMock()):
        pass

    mock_init.assert_not_called()
    fake_http_client.aclose.assert_awaited_once()
    fake_firestore.close.assert_awaited_once()
    _mock_setup.assert_called_once()
