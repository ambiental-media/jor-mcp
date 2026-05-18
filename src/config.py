"""Application configuration constants.

All values are sourced from environment variables. Defaults are safe
for local development; production deployments must override them via
Cloud Run environment variable configuration.
"""

import os

# ---------------------------------------------------------------------------
# Redis / Rate Limiting
# ---------------------------------------------------------------------------

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
"""Full Redis connection URL.  Example: redis://10.0.0.1:6379/0"""

REDIS_SOCKET_TIMEOUT: float = float(os.environ.get("REDIS_SOCKET_TIMEOUT", "1.0"))
"""Seconds to wait for a Redis command before timing out (fail-open)."""

REDIS_CONNECT_TIMEOUT: float = float(os.environ.get("REDIS_CONNECT_TIMEOUT", "1.0"))
"""Seconds to wait when opening a new Redis connection."""

# Rate-limit quotas per tier: monthly request allowance (Fixed Window)
RATE_LIMIT_BASIC: int = int(os.environ.get("RATE_LIMIT_BASIC_REQUESTS", "500"))
"""Monthly request quota for 'basic' tier users."""

RATE_LIMIT_PRO: int = int(os.environ.get("RATE_LIMIT_PRO_REQUESTS", "2000"))
"""Monthly request quota for 'pro' tier users."""

# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

HTTP_TIMEOUT: float = float(os.environ.get("HTTP_TIMEOUT", "10.0"))
"""Default timeout in seconds applied to all outbound HTTP requests."""

HTTP_MAX_KEEPALIVE_CONNECTIONS: int = int(os.environ.get("HTTP_MAX_KEEPALIVE_CONNECTIONS", "50"))
"""Maximum number of idle keep-alive connections retained in the pool."""

HTTP_MAX_CONNECTIONS: int = int(os.environ.get("HTTP_MAX_CONNECTIONS", "100"))
"""Maximum total concurrent connections allowed in the pool."""

# ---------------------------------------------------------------------------
# WordPress REST API
# ---------------------------------------------------------------------------

WP_API_BASE_URL: str = os.environ.get(
    "WORDPRESS_API_URL", "https://ambiental.media/wp-json"
).rstrip("/")
"""Base URL for the WordPress REST API (no trailing slash).

Example: https://ambiental.media/wp-json
"""
