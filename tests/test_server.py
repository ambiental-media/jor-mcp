from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient


def _make_fake_redis() -> MagicMock:
    """Return a MagicMock that satisfies the Redis async interface."""
    fake_redis = MagicMock()
    pipeline_rv = fake_redis.pipeline.return_value
    pipeline_rv.__aenter__ = AsyncMock(return_value=pipeline_rv)
    pipeline_rv.__aexit__ = AsyncMock(return_value=False)
    pipeline_rv.execute = AsyncMock(return_value=[0, 0, 1, True])
    fake_redis.zrange = AsyncMock(return_value=[])
    fake_redis.aclose = AsyncMock()
    return fake_redis


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

    fake_redis = _make_fake_redis()
    fake_http_client = AsyncMock()
    with (
        patch("firebase_admin.get_app", side_effect=ValueError("No app")),
        patch("firebase_admin.initialize_app") as mock_init,
        patch("src.server._mcp_http_app") as mock_mcp_app,
        patch("redis.asyncio.ConnectionPool.from_url", return_value=MagicMock()),
        patch("redis.asyncio.Redis", return_value=fake_redis),
        patch("httpx.AsyncClient", return_value=fake_http_client),
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

    fake_redis = _make_fake_redis()
    fake_http_client = AsyncMock()
    with (
        patch("firebase_admin.get_app", return_value=MagicMock()),
        patch("firebase_admin.initialize_app") as mock_init,
        patch("src.server._mcp_http_app") as mock_mcp_app,
        patch("redis.asyncio.ConnectionPool.from_url", return_value=MagicMock()),
        patch("redis.asyncio.Redis", return_value=fake_redis),
        patch("httpx.AsyncClient", return_value=fake_http_client),
    ):
        mock_mcp_app.lifespan = fake_mcp_lifespan
        async with server_lifespan(MagicMock()):
            pass

    mock_init.assert_not_called()
