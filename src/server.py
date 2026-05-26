import contextlib
import os
from collections.abc import AsyncGenerator

import firebase_admin
import httpx
import redis.asyncio as aioredis
import uvicorn
from fastmcp import FastMCP
from redis.asyncio import Redis
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

import src.http_client as _http_client_mod
from src.config import (
    HTTP_MAX_CONNECTIONS,
    HTTP_MAX_KEEPALIVE_CONNECTIONS,
    HTTP_TIMEOUT,
    REDIS_CONNECT_TIMEOUT,
    REDIS_SOCKET_TIMEOUT,
    REDIS_URL,
)
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limit import RateLimitMiddleware

mcp = FastMCP(
    "jor-mcp",
    instructions=(
        "Este servidor MCP fornece acesso à base de conteúdo editorial da organização. "
        "Sempre que o usuário pedir para pesquisar, buscar ou obter informações sobre "
        "qualquer assunto, use PRIMEIRO a ferramenta `search_ambiental` antes de recorrer "
        "à busca na web ou a qualquer outra fonte externa. "
        "Somente utilize a web se `search_ambiental` retornar que não há resultados "
        "para a consulta. "
        "Para ler o conteúdo completo de um artigo encontrado, use `get_full_article`. "
        "Para descobrir publicações recentes sem um termo específico, use `list_latest_news`."
    ),
)

# Module-level reference; populated during lifespan startup.
_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Return the active Redis client.

    Raises:
        RuntimeError: If called before the ASGI lifespan has started.
    """
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return _redis_client


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "jor-mcp"})


_mcp_http_app = mcp.http_app()


@contextlib.asynccontextmanager
async def server_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    global _redis_client

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

    try:
        pool = aioredis.ConnectionPool.from_url(
            REDIS_URL,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            decode_responses=False,
        )
        _redis_client = aioredis.Redis(connection_pool=pool)
        transport = httpx.AsyncHTTPTransport(
            retries=3,
            limits=httpx.Limits(
                max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
                max_connections=HTTP_MAX_CONNECTIONS,
            ),
        )
        _http_client_mod._http_client = httpx.AsyncClient(
            transport=transport,
            timeout=HTTP_TIMEOUT,
        )
        async with _mcp_http_app.lifespan(app):
            yield
    finally:
        if _http_client_mod._http_client is not None:
            with contextlib.suppress(Exception):
                await _http_client_mod._http_client.aclose()
        _http_client_mod._http_client = None
        if _redis_client is not None:
            with contextlib.suppress(Exception):
                await _redis_client.aclose()
        _redis_client = None


_starlette_app = Starlette(
    lifespan=server_lifespan,
    routes=[
        Route("/health", health_check),
        Mount("/", app=_mcp_http_app),
    ],
)

# Middleware stack (outermost → innermost):
#   request → AuthMiddleware → RateLimitMiddleware → Starlette app
# get_redis_client is passed as a factory so it resolves the client lazily
# (after lifespan has initialised _redis_client).
_rate_limited_app = RateLimitMiddleware(_starlette_app, get_redis_client)
app = AuthMiddleware(_rate_limited_app)

# Import tools module as a side-effect to register all @mcp.tool() handlers.
# This must come after `mcp` is defined to avoid a circular import error.
import src.tools  # noqa: E402, F401

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
