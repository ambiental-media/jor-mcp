import contextlib
import os
from collections.abc import AsyncGenerator

import firebase_admin
import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from src.middleware.auth import AuthMiddleware

mcp = FastMCP("jor-mcp")


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "jor-mcp"})


_mcp_http_app = mcp.http_app()


@contextlib.asynccontextmanager
async def server_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

    async with _mcp_http_app.lifespan(app):
        yield


_starlette_app = Starlette(
    lifespan=server_lifespan,
    routes=[
        Route("/health", health_check),
        Mount("/", app=_mcp_http_app),
    ],
)

app = AuthMiddleware(_starlette_app)

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
