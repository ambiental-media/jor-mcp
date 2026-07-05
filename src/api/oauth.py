"""OAuth 2.1 proxy API router.

RESTful endpoints backing the native MCP OAuth 2.1 flow (Dynamic Client
Registration, PKCE challenge storage, token exchange and consent approval).
These routes are mounted under the ``/api/oauth`` prefix by :mod:`src.server`
(plus the root ``/.well-known`` discovery routes) and are intentionally exempt
from Firebase authentication: they are the very mechanism through which clients
obtain Firebase tokens, so requiring a token to reach them would be circular.
"""

import json
import logging
import uuid
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from google.cloud import firestore
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.config import (
    OAUTH_CLIENTS_COLLECTION,
    OAUTH_PORTAL_BASE_URL,
    OAUTH_SERVER_BASE_URL,
)

logger = logging.getLogger(__name__)

OAUTH_PATH_PREFIX = "/api/oauth"
"""Mount prefix for the OAuth proxy router (single source of truth)."""

WELL_KNOWN_PREFIX = "/.well-known"
"""Root prefix for the OAuth discovery metadata routes."""


def is_oauth_path(path: str) -> bool:
    """Return True if *path* targets an auth-exempt OAuth route.

    Covers both the proxy router (``/api/oauth``) and the discovery metadata
    (``/.well-known``). Used by the authentication middleware to bypass Firebase
    token validation: these routes are the mechanism through which clients obtain
    Firebase tokens, so requiring one to reach them would be circular.

    Args:
        path: The request path taken from the ASGI scope.

    Returns:
        True when the path is part of the OAuth proxy or discovery surface.
    """
    return (
        path == OAUTH_PATH_PREFIX
        or path.startswith(f"{OAUTH_PATH_PREFIX}/")
        or path.startswith(f"{WELL_KNOWN_PREFIX}/")
    )


class ClientRegistrationRequest(BaseModel):
    """Validated subset of an RFC 7591 Dynamic Client Registration payload.

    Unknown fields sent by MCP clients are ignored rather than rejected.
    """

    model_config = ConfigDict(extra="ignore")

    redirect_uris: list[str] = Field(min_length=1)
    client_name: str | None = None
    token_endpoint_auth_method: str | None = None
    grant_types: list[str] | None = None
    response_types: list[str] | None = None
    scope: str | None = None


def _error_response(error: str, description: str, status_code: int) -> JSONResponse:
    """Build a standard OAuth error JSON response."""
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status_code,
    )


def _normalize_loopback(uri: str) -> str:
    """Rewrite a ``127.0.0.1`` loopback host to ``localhost``.

    MCP clients are inconsistent about which loopback form they register versus
    redirect to; normalizing both to ``localhost`` at registration time avoids
    redirect_uri mismatches during the token exchange (Task 5).

    Args:
        uri: A redirect URI as supplied by the client.

    Returns:
        The URI with a ``127.0.0.1`` host replaced by ``localhost``; otherwise
        the URI unchanged.
    """
    parts = urlsplit(uri)
    if parts.hostname != "127.0.0.1":
        return uri
    netloc = "localhost" if parts.port is None else f"localhost:{parts.port}"
    normalized: SplitResult = parts._replace(netloc=netloc)
    return urlunsplit(normalized)


async def oauth_health(request: Request) -> JSONResponse:
    """Liveness probe for the OAuth proxy router."""
    return JSONResponse({"status": "ok", "service": "jor-mcp-oauth"})


async def authorization_server_metadata(request: Request) -> JSONResponse:
    """RFC 8414 Authorization Server Metadata for native MCP OAuth discovery.

    The ``authorization_endpoint`` points at the Next.js consent portal while the
    token and registration endpoints point at this Python backend.
    """
    return JSONResponse(
        {
            "issuer": OAUTH_SERVER_BASE_URL,
            "authorization_endpoint": f"{OAUTH_PORTAL_BASE_URL}/authorize",
            "token_endpoint": f"{OAUTH_SERVER_BASE_URL}{OAUTH_PATH_PREFIX}/token",
            "registration_endpoint": f"{OAUTH_SERVER_BASE_URL}{OAUTH_PATH_PREFIX}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )


async def protected_resource_metadata(request: Request) -> JSONResponse:
    """RFC 9728 Protected Resource Metadata pointing clients at the auth server."""
    return JSONResponse(
        {
            "resource": f"{OAUTH_SERVER_BASE_URL}/mcp",
            "authorization_servers": [OAUTH_SERVER_BASE_URL],
        }
    )


async def oauth_register(request: Request) -> JSONResponse:
    """Dynamic Client Registration endpoint (RFC 7591).

    Validates the client metadata, forces the client to be public
    (``token_endpoint_auth_method = "none"``), normalizes loopback redirect URIs,
    persists the client under :data:`OAUTH_CLIENTS_COLLECTION` and returns the
    generated ``client_id``.
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return _error_response("invalid_request", "Request body must be valid JSON", 400)

    try:
        metadata = ClientRegistrationRequest.model_validate(payload)
    except ValidationError as exc:
        return _error_response("invalid_client_metadata", str(exc), 400)

    redirect_uris = [_normalize_loopback(uri) for uri in metadata.redirect_uris]
    client_id = str(uuid.uuid4())
    document: dict[str, Any] = {
        "client_id": client_id,
        "client_name": metadata.client_name,
        "redirect_uris": redirect_uris,
        # Business rule: MCP clients must be public regardless of what they ask for.
        "token_endpoint_auth_method": "none",  # nosec B105
        "grant_types": metadata.grant_types or ["authorization_code", "refresh_token"],
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    # Lazy import: src.server imports this module's routes at load time, so a
    # top-level `from src.server import ...` here would be a circular import.
    from src.server import get_firestore_client

    db = get_firestore_client()
    await db.collection(OAUTH_CLIENTS_COLLECTION).document(client_id).set(document)

    logger.info("Registered OAuth client", extra={"client_id": client_id})

    return JSONResponse(
        {
            "client_id": client_id,
            "client_name": metadata.client_name,
            "redirect_uris": redirect_uris,
            "token_endpoint_auth_method": "none",  # nosec B105
        },
        status_code=201,
    )


routes: list[Route] = [
    Route("/health", oauth_health, methods=["GET"]),
    Route("/register", oauth_register, methods=["POST"]),
]
"""Routes mounted under :data:`OAUTH_PATH_PREFIX` (``/api/oauth``)."""

well_known_routes: list[Route] = [
    Route(
        "/.well-known/oauth-authorization-server",
        authorization_server_metadata,
        methods=["GET"],
    ),
    Route(
        "/.well-known/oauth-protected-resource",
        protected_resource_metadata,
        methods=["GET"],
    ),
]
"""Discovery routes mounted at the application root by :mod:`src.server`."""
