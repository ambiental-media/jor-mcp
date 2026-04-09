import os

import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

mcp = FastMCP("jor-mcp")


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "jor-mcp"})


app = Starlette(
    routes=[
        Route("/health", health_check),
        Mount("/", app=mcp.http_app()),
    ]
)

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
