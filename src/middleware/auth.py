import logging
from typing import Any, cast

import firebase_admin
import firebase_admin.exceptions
from firebase_admin import auth
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"


class AuthMiddleware:
    """ASGI middleware that validates Firebase ID tokens for all incoming requests.

    Requests to /health bypass validation to allow Cloud Run health checks.
    On success, injects scope["user"] = {"uid": ..., "tier": ...} for downstream
    middleware (e.g. RateLimitMiddleware) to consume.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope.get("path") == _HEALTH_PATH:
            await self.app(scope, receive, send)
            return

        raw_headers = cast(list[tuple[bytes, bytes]], scope.get("headers", []))
        header_map: dict[bytes, bytes] = {k.lower(): v for k, v in raw_headers}
        auth_header = header_map.get(b"authorization", b"").decode("utf-8")

        token = auth_header[len("Bearer ") :] if auth_header.startswith("Bearer ") else ""
        if not token:
            logger.warning(
                "Missing or malformed Authorization header for path: %s",
                scope.get("path"),
            )
            await _send_unauthorized(send)
            return

        try:
            decoded_token: dict[str, Any] = auth.verify_id_token(token, clock_skew_seconds=60)
        except (firebase_admin.exceptions.FirebaseError, ValueError) as exc:
            logger.warning("Firebase token verification failed: %s", exc)
            await _send_unauthorized(send)
            return

        scope["user"] = {
            "uid": decoded_token["uid"],
            "tier": decoded_token.get("tier", "basic"),
        }

        await self.app(scope, receive, send)


async def _send_unauthorized(send: Send) -> None:
    """Send a standardized HTTP 401 Unauthorized ASGI response."""
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail": "Unauthorized"}',
            "more_body": False,
        }
    )
