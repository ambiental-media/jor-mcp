import logging
import time
from collections import defaultdict

import jwt
import uvicorn
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.app import mcp
from src.config import (
    JWT_SECRET,
    LOG_LEVEL,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    PORT,
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
)
from src.telemetry import get_tracer, setup_telemetry

import src.tools

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=(
        '{"time":"%(asctime)s","level":"%(levelname)s",'
        '"logger":"%(name)s","message":"%(message)s"}'
    ),
)
logger = logging.getLogger("jor-mcp")

setup_telemetry(otlp_endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)


class MCPMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        if path == "/health":
            resp = JSONResponse({"status": "ok", "service": "jor-mcp"})
            await resp(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.time()

        tracer = get_tracer()
        method = scope.get("method", "")
        with tracer.start_as_current_span(f"{method} {path}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.path", path)
            span.set_attribute("client.address", client_ip)

            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if now - t < RATE_LIMIT_WINDOW
            ]

            if len(self._requests[client_ip]) >= RATE_LIMIT_MAX:
                logger.warning("Rate limit exceeded for %s", client_ip)
                span.set_attribute("http.status_code", 429)
                resp = JSONResponse(
                    {"error": "Too many requests. Please try again later."},
                    status_code=429,
                )
                await resp(scope, receive, send)
                return

            self._requests[client_ip].append(now)

            if JWT_SECRET:
                headers = dict(scope.get("headers", []))
                auth = headers.get(b"authorization", b"").decode()

                if not auth.startswith("Bearer "):
                    logger.warning("Missing auth header from %s on %s", client_ip, path)
                    span.set_attribute("http.status_code", 401)
                    resp = JSONResponse(
                        {"error": "Missing or invalid Authorization header"},
                        status_code=401,
                    )
                    await resp(scope, receive, send)
                    return

                token = auth[7:]
                try:
                    jwt.decode(
                        token,
                        JWT_SECRET,
                        algorithms=["HS256"],
                        options={"require": ["exp"]},
                    )
                except jwt.InvalidTokenError:
                    logger.warning("Invalid JWT from %s on %s", client_ip, path)
                    span.set_attribute("http.status_code", 401)
                    resp = JSONResponse(
                        {"error": "Invalid token"}, status_code=401
                    )
                    await resp(scope, receive, send)
                    return

            await self.app(scope, receive, send)


mcp_http = mcp.http_app()
app = MCPMiddleware(mcp_http)

logger.info("Jor-MCP server configured on port %d", PORT)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)