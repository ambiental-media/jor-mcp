# Infrastructure & Deployment

This document outlines the deployment architecture for the Jor-MCP server on Google Cloud Platform (GCP).

## 1. GCP Architecture Overview

The system is designed to be fully serverless, highly available, and stateless at the application layer.

- **Entrypoint:** Global External Application Load Balancer (Handles custom domains, SSL, and SSE streaming).
- **Compute:** Google Cloud Run (Containerized, auto-scaling). Locked down to "Internal and Cloud Load Balancing traffic only."
- **Database/State:** Google Cloud Firestore (Handles distributed rate-limiting via atomic increments).
- **Identity:** Google Cloud Identity Platform / Firebase Auth (Validates JWTs).
- **Observability:** Google Cloud Operations Suite (Cloud Logging and Cloud Trace via OpenTelemetry).

## 2. Environment Variables

The server relies strictly on environment variables for configuration. No secrets are hardcoded. In GCP, these should be injected via Google Secret Manager into Cloud Run.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PORT` | The port the ASGI server binds to. | `8080` |
| `LOG_LEVEL` | Python logging level (`INFO`, `DEBUG`, `WARNING`). | `INFO` |
| `FIREBASE_PROJECT_ID` | The GCP Project ID associated with Firebase Auth. | *(Required)* |
| `GCP_PROJECT_ID` | GCP project ID used to emit `logging.googleapis.com/trace` in Cloud Logging format. Falls back to `GOOGLE_CLOUD_PROJECT` when omitted. | *(Optional in Cloud Run, recommended elsewhere)* |
| `WORDPRESS_API_URL` | Base URL for the main WordPress REST API. | `https://ambiental.media/wp-json/wp/v2` |
| `MCP_GITHUB_TOKEN` | Personal Access Token to read private Next.js repos. | *(Required)* |
| `MCP_GITHUB_REPOS` | Comma-separated list of Next.js repos (e.g., `mata-nativa,rio60`). | *(Required)* |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| OTLP endpoint for tracing. Empty means console export. | `""` |

> **Note on Rate Limiting (Firestore):** The application relies on Google Cloud Firestore for its state. It automatically utilizes Google Application Default Credentials (ADC) bound to the Cloud Run service account. No explicit connection string or secret is required, but the service account *must* be granted the `roles/datastore.user` IAM role.

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

## 5. Declarative Service Manifest

The Cloud Run service is managed declaratively via a `service.yaml` file located at the root of the repository. This file is the single source of truth for the service configuration, including container resources, auto-scaling, ingress, and environment variables.

Sensitive variables (`MCP_GITHUB_TOKEN`, `REDIS_URL`, `JWT_SECRET`) are never hardcoded in the YAML. They are stored in GCP Secret Manager and injected directly into the container at runtime via `valueFrom: secretKeyRef`.

### Applying the manifest locally

Export the required environment variables and use `envsubst` to replace the placeholders before applying:

```bash
export IMAGE_URL="us-central1-docker.pkg.dev/jor-mcp/jor-mcp/jor-mcp-server:SHA"
export GCP_PROJECT_NUMBER="959918358302"
export GCP_PROJECT_ID="jor-mcp"
export FIREBASE_PROJECT_ID="..."
export WORDPRESS_API_URL="..."
export MCP_GITHUB_REPOS="..."
export OTEL_EXPORTER_OTLP_ENDPOINT="..."

envsubst < service.yaml | gcloud run services replace - --region us-central1
```

### In the CD pipeline (GitHub Actions)

The variables above are injected automatically as repository secrets and variables. The `envsubst` command is executed by the pipeline before calling `gcloud run services replace`, so no manual substitution is needed.