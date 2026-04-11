# Infrastructure & Deployment

This document outlines the deployment architecture for the Jor-MCP server on Google Cloud Platform (GCP).

## 1. GCP Architecture Overview

The system is designed to be fully serverless, highly available, and stateless at the application layer.

- **Entrypoint:** Global External Application Load Balancer (Handles custom domains, SSL, and SSE streaming).
- **Compute:** Google Cloud Run (Containerized, auto-scaling). Locked down to "Internal and Cloud Load Balancing traffic only."
- **Cache/State:** Google Cloud Memorystore for Redis (Handles distributed rate-limiting).
- **Identity:** Google Cloud Identity Platform / Firebase Auth (Validates JWTs).
- **Observability:** Google Cloud Operations Suite (Cloud Logging and Cloud Trace via OpenTelemetry).

## 2. Environment Variables

The server relies strictly on environment variables for configuration. No secrets are hardcoded. In GCP, these should be injected via Google Secret Manager into Cloud Run.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PORT` | The port the ASGI server binds to. | `8080` |
| `LOG_LEVEL` | Python logging level (`INFO`, `DEBUG`, `WARNING`). | `INFO` |
| `REDIS_URL` | Connection string for GCP Memorystore (e.g., `redis://10.0.0.3:6379`). | *(Required)* |
| `FIREBASE_PROJECT_ID` | The GCP Project ID associated with Firebase Auth. | *(Required)* |
| `WORDPRESS_API_URL` | Base URL for the main WordPress REST API. | `https://ambiental.media/wp-json/wp/v2` |
| `GITHUB_TOKEN` | Personal Access Token to read private Next.js repos. | *(Required)* |
| `GITHUB_REPOS` | Comma-separated list of Next.js repos (e.g., `mata-nativa,rio60`). | *(Required)* |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| OTLP endpoint for tracing. Empty means console export. | `""` |

## 3. Dockerization Strategy

We use a multi-stage `Dockerfile` to keep the production image secure and lightweight.

1. **Builder Stage:** Uses the `uv` package manager to resolve and install dependencies into an isolated virtual environment (`.venv`).
2. **Runtime Stage:** Copies only the `.venv` and the `src/` directory into a slim Python base image. It runs the application as a non-root user (`appuser`) to comply with container security best practices.

## 4. Deployment Pipeline

Deployment should be automated via GitHub Actions:
1. Triggered on push to the `main` branch.
2. Runs `make check` (Tests, Linting, Type checking).
3. Builds the Docker image.
4. Pushes the image to Google Artifact Registry.
5. Deploys the new revision to Cloud Run using the existing service account.
