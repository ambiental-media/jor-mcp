
import os

# Server
PORT = int(os.environ.get("PORT", "8080"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

JWT_SECRET = os.environ.get("JWT_SECRET", "")

RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "60"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60")) 

WORDPRESS_API_URL = os.environ.get(
    "WORDPRESS_API_URL",
    "https://ambiental.media/wp-json/wp/v2",
)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOS = [
    r.strip()
    for r in os.environ.get("GITHUB_REPOS", "").split(",")
    if r.strip()
]

# ─── OpenTelemetry ────────────────────────────────────────────
# Deixe vazio para usar console exporter (modo dev).
# Em produção aponte para o endpoint do OTLP collector / Cloud Trace.
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

