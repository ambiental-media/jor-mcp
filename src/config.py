"""Application configuration constants.

All values are sourced from environment variables. Defaults are safe
for local development; production deployments must override them via
Cloud Run environment variable configuration.
"""

import os

# ---------------------------------------------------------------------------
# Firestore / Rate Limiting
# ---------------------------------------------------------------------------

FIRESTORE_DATABASE_ID: str = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")
"""Firestore database ID. Override when using a named database (e.g. 'jor-mcp')."""

RATE_LIMIT_COLLECTION: str = os.environ.get("RATE_LIMIT_COLLECTION", "rate_limits")
"""Firestore collection used to store monthly fixed-window user counters."""

# Rate-limit quotas per tier: monthly request allowance (Fixed Window)
RATE_LIMIT_BASIC: int = int(os.environ.get("RATE_LIMIT_BASIC_REQUESTS", "500"))
"""Monthly request quota for 'basic' tier users."""
RATE_LIMIT_PRO: int = int(os.environ.get("RATE_LIMIT_PRO_REQUESTS", "2000"))
"""Monthly request quota for 'pro' tier users."""

# ---------------------------------------------------------------------------
# CORS (OAuth consent portal)
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,https://jor-mcp.ambiental.media",
    ).split(",")
    if origin.strip()
]
"""Browser origins allowed to call the OAuth proxy endpoints via CORS.

Comma-separated list provided through the ``CORS_ALLOWED_ORIGINS`` environment
variable. Defaults to the local Next.js dev portal (``http://localhost:3000``)
and the production consent portal (``https://jor-mcp.ambiental.media``).
"""

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

WP_API_BASE_URL: str = (
    os.environ.get("WORDPRESS_API_URL", "https://ambiental.media/wp-json")
    .rstrip("/")
    .removesuffix("/wp/v2")
)
"""Base URL for the WordPress REST API (no trailing slash, without /wp/v2).

Accepts both ``https://ambiental.media/wp-json`` and
``https://ambiental.media/wp-json/wp/v2`` — the ``/wp/v2`` suffix is
normalised away so service code can safely append ``/wp/v2/<resource>``.
"""

# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

GITHUB_TOKEN: str | None = os.environ.get("MCP_GITHUB_TOKEN")
"""Personal Access Token for the GitHub API. Optional for public repos.

Environment variable: ``MCP_GITHUB_TOKEN``.
"""

GITHUB_REPOS: str = os.environ.get("MCP_GITHUB_REPOS", "")
"""Comma-separated list of GitHub repositories (owner/repo format) to index.

Example: ambiental-media/microsite-amazonia,ambiental-media/microsite-pantanal

Environment variable: ``MCP_GITHUB_REPOS``.
"""

GITHUB_API_BASE_URL: str = os.environ.get(
    "MCP_GITHUB_API_BASE_URL", "https://api.github.com"
).rstrip("/")
"""Base URL for the GitHub REST API (no trailing slash).

Environment variable: ``MCP_GITHUB_API_BASE_URL``.
"""

# ---------------------------------------------------------------------------
# OpenTelemetry
# ---------------------------------------------------------------------------

OTEL_EXPORTER_OTLP_ENDPOINT: str | None = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
"""OTLP/HTTP collector endpoint for exporting traces (e.g. http://localhost:4318).

When absent the SDK falls back to :class:`ConsoleSpanExporter` which writes
spans to stdout – useful for local development.
"""

OTEL_SERVICE_NAME: str = os.environ.get("OTEL_SERVICE_NAME", "jor-mcp")
"""Logical service name embedded in every exported span's resource attributes."""

GCP_PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
"""Google Cloud project ID used to build Cloud Logging trace correlation fields.

When set, log records include ``logging.googleapis.com/trace`` in the
``projects/<project-id>/traces/<trace-id>`` format required by Cloud Logging.
"""
