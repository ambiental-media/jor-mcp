import asyncio
import logging
from typing import Any, cast

import firebase_admin
import firebase_admin.exceptions
from firebase_admin import auth
from pydantic import BaseModel, ValidationError
from starlette.types import ASGIApp, Receive, Scope, Send

from src.api.oauth import is_oauth_path
from src.config import OAUTH_SERVER_BASE_URL

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"

# RFC 9728 §5.1: a 401 from the resource server must advertise where the protected
# resource metadata lives, so MCP clients can discover the authorization server and
# start the OAuth flow (this is what makes Claude Desktop open the login browser).
_RESOURCE_METADATA_URL = f"{OAUTH_SERVER_BASE_URL}/.well-known/oauth-protected-resource"
_WWW_AUTHENTICATE = f'Bearer resource_metadata="{_RESOURCE_METADATA_URL}"'


class DecodedToken(BaseModel):
    """Pydantic model for runtime validation of the Firebase decoded JWT payload."""

    uid: str
    email: str | None = None
    tier: str = "basic"


class AuthMiddleware:
    """ASGI middleware that validates Firebase ID tokens for all incoming requests.

    Requests to /health bypass validation to allow Cloud Run health checks, and
    requests under the OAuth proxy prefix (/api/oauth) or the discovery metadata
    (/.well-known) bypass it because they are the mechanism through which clients
    obtain Firebase tokens in the first place.
    On success, injects scope["user"] = {"uid": ..., "tier": ...} for downstream
    middleware (e.g. RateLimitMiddleware) to consume.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == _HEALTH_PATH or is_oauth_path(path):
            await self.app(scope, receive, send)
            return

        raw_headers = cast(list[tuple[bytes, bytes]], scope.get("headers", []))
        header_map: dict[bytes, bytes] = {k.lower(): v for k, v in raw_headers}
        auth_header = header_map.get(b"authorization", b"").decode("utf-8", errors="ignore")

        token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""
        if not token:
            logger.warning(
                "Missing or malformed Authorization header",
                extra={"path": scope.get("path")},
            )
            await _send_unauthorized(send)
            return

        try:
            decoded_dict: dict[str, Any] = await asyncio.to_thread(
                auth.verify_id_token, token, clock_skew_seconds=60
            )
            decoded_token = DecodedToken.model_validate(decoded_dict)
        except (firebase_admin.exceptions.FirebaseError, ValueError, ValidationError) as exc:
            logger.warning("Firebase token verification failed", extra={"error": str(exc)})
            await _send_unauthorized(send)
            return

        scope["user"] = {
            "uid": decoded_token.uid,
            "tier": decoded_token.tier,
        }

        await self.app(scope, receive, send)


async def _send_unauthorized(send: Send) -> None:
    """Send a standardized HTTP 401 Unauthorized ASGI response."""
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", _WWW_AUTHENTICATE.encode("ascii")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail": "Unauthorized"}',
            "more_body": False,
        }
    )
