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

# Rate-limit quotas per tier: (max_requests, window_seconds)
RATE_LIMIT_BASIC: tuple[int, int] = (
    int(os.environ.get("RATE_LIMIT_BASIC_REQUESTS", "20")),
    int(os.environ.get("RATE_LIMIT_BASIC_WINDOW", "60")),
)
"""Quota for 'basic' tier users: (requests, window_in_seconds)."""

RATE_LIMIT_PRO: tuple[int, int] = (
    int(os.environ.get("RATE_LIMIT_PRO_REQUESTS", "100")),
    int(os.environ.get("RATE_LIMIT_PRO_WINDOW", "60")),
)
"""Quota for 'pro' tier users: (requests, window_in_seconds)."""
