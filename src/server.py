import os

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

_starlette_app = Starlette(
    lifespan=_mcp_http_app.lifespan,
    routes=[
        Route("/health", health_check),
        Mount("/", app=_mcp_http_app),
    ],
)

app = AuthMiddleware(_starlette_app)

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
