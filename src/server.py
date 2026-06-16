import contextlib
import logging
import os
from collections.abc import AsyncGenerator

import firebase_admin
import httpx
import redis.asyncio as aioredis
import uvicorn
from fastmcp import FastMCP
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.applications import Starlette
from starlette.middleware import Middleware
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
from src.telemetry import instrument_asgi_app, setup_telemetry

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "jor-mcp",
    instructions=(
        "Você é um assistente jornalístico especializado na base de conteúdo da organização "
        "que configurou este servidor MCP. Sua função é consultar e apresentar o conteúdo "
        "editorial publicado por essa organização — matérias, reportagens e dados — com "
        "precisão e rigor jornalístico.\n\n"
        "REGRA ZERO — NUNCA quebre esta regra: não alucine dados, números, datas, nomes "
        "de pessoas ou organizações. Cite sempre a fonte exata (título do artigo, URL e "
        "data de publicação) de onde cada informação foi extraída. Se não encontrar a "
        "informação na base de dados, diga explicitamente ao usuário que não há registros "
        "disponíveis e sugira outros termos de busca.\n\n"
        "FLUXO DE TRABALHO OBRIGATÓRIO:\n"
        "1. Sempre que o usuário pedir para pesquisar, buscar ou obter informações sobre "
        "qualquer assunto, chame PRIMEIRO a ferramenta `search_content` antes de recorrer "
        "à busca na web ou a qualquer outra fonte externa.\n"
        "2. Somente utilize a web ou seu conhecimento interno se `search_content` retornar "
        "explicitamente que não há resultados para a consulta.\n"
        "3. Para ler o texto integral de uma matéria encontrada, chame `get_full_article` "
        "com o link ou ID retornado pela busca.\n"
        "4. Para descobrir publicações recentes sem um termo de busca específico, chame "
        "`list_latest_news`.\n\n"
        "TOM E ESTILO: priorize precisão factual e clareza jornalística. "
        "Apresente os resultados de forma estruturada, destacando "
        "título, data de publicação e link da fonte."
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

    setup_telemetry()

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
            with contextlib.suppress(OSError, RuntimeError):
                await _http_client_mod._http_client.aclose()
        _http_client_mod._http_client = None
        if _redis_client is not None:
            with contextlib.suppress(RedisError):
                await _redis_client.aclose()
        _redis_client = None


_starlette_app = Starlette(
    lifespan=server_lifespan,
    middleware=[
        Middleware(AuthMiddleware),
        Middleware(RateLimitMiddleware, redis_factory=get_redis_client),
    ],
    routes=[
        Route("/health", health_check),
        Mount("/", app=_mcp_http_app),
    ],
)

# instrument_asgi_app() must be called before the application starts: Starlette
# forbids add_middleware() after startup.  OTel's ProxyTracer mechanism ensures
# that spans are correlated with the real TracerProvider configured later inside
# server_lifespan.  Final middleware order (outermost first):
#   OTel → AuthMiddleware → RateLimitMiddleware → routes
instrument_asgi_app(_starlette_app)

app = _starlette_app

# Import tools module as a side-effect to register all @mcp.tool() handlers.
# This must come after `mcp` is defined to avoid a circular import error.
import src.tools  # noqa: E402, F401

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
