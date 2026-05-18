"""Global async HTTP client singleton managed by the ASGI lifespan."""

import logging

import httpx

logger = logging.getLogger(__name__)

# Module-level reference; populated during lifespan startup.
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the active async HTTP client.

    The instance is created once during ASGI lifespan startup (in
    ``src.server.server_lifespan``) and reused for the entire lifetime of the
    worker process, enabling connection pooling across all MCP tool calls.

    Returns:
        The shared ``httpx.AsyncClient`` instance.

    Raises:
        RuntimeError: If called before the ASGI lifespan has started.
    """
    if _http_client is None:
        raise RuntimeError("HTTP client is not initialized")
    return _http_client
