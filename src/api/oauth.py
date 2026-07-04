"""OAuth 2.1 proxy API router.

RESTful endpoints backing the native MCP OAuth 2.1 flow (Dynamic Client
Registration, PKCE challenge storage, token exchange and consent approval).
These routes are mounted under the ``/api/oauth`` prefix by :mod:`src.server`
and are intentionally exempt from Firebase authentication: they are the very
mechanism through which clients obtain Firebase tokens, so requiring a token
to reach them would be circular.
"""

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)

OAUTH_PATH_PREFIX = "/api/oauth"
"""Mount prefix for the OAuth proxy router (single source of truth)."""


def is_oauth_path(path: str) -> bool:
    """Return True if *path* targets the OAuth proxy router.

    Used by the authentication middleware to bypass Firebase token validation
    for these routes: they are the mechanism through which clients obtain
    Firebase tokens, so requiring one to reach them would be circular.

    Args:
        path: The request path taken from the ASGI scope.

    Returns:
        True when the path equals the mount prefix or sits beneath it.
    """
    return path == OAUTH_PATH_PREFIX or path.startswith(f"{OAUTH_PATH_PREFIX}/")


async def oauth_health(request: Request) -> JSONResponse:
    """Liveness probe for the OAuth proxy router."""
    return JSONResponse({"status": "ok", "service": "jor-mcp-oauth"})


routes: list[Route] = [
    Route("/health", oauth_health, methods=["GET"]),
]
