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
| `WORDPRESS_API_URL` | Base URL for the main WordPress REST API. | `https://ambiental.media/wp-json/wp/v2` |
| `GITHUB_TOKEN` | Personal Access Token to read private Next.js repos. | *(Required)* |
| `GH_REPOS` | Comma-separated list of GitHub repos in `owner/repo` format (e.g., `ambiental-media/Cerrado,ambiental-media/rio-60`). Named `GH_REPOS` (not `GITHUB_REPOS`) because GitHub Actions forbids variables prefixed with `GITHUB_`. | *(Required)* |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| OTLP endpoint for tracing. Empty means console export. | `""` |

> **Note on Rate Limiting (Firestore):** The application relies on Google Cloud Firestore for its state. It automatically utilizes Google Application Default Credentials (ADC) bound to the Cloud Run service account. No explicit connection string or secret is required, but the service account *must* be granted the `roles/datastore.user` IAM role.

## 3. Dockerization Strategy

We use a multi-stage `Dockerfile` to keep the production image secure and lightweight.

1. **Builder Stage:** Uses the `uv` package manager to resolve and install dependencies into an isolated virtual environment (`.venv`).
2. **Runtime Stage:** Copies only the `.venv` and the `src/` directory into a slim Python base image. It runs the application as a non-root user (`appuser`) to comply with container security best practices.

## 4. CI/CD Pipeline

The pipeline is split into two GitHub Actions workflows with distinct triggers and responsibilities.

### Continuous Integration — `.github/workflows/ci.yml`

Triggered automatically on every Pull Request. After the quality and security checks pass, it builds the Docker image, scans it with Trivy, and pushes it to Google Artifact Registry tagged with the originating Pull Request number (`:pr-<number>`). This per-PR tag replaces the previous static `:test` tag, avoiding a race condition when multiple PRs build simultaneously.

### Continuous Deployment — `.github/workflows/cd.yml`

Triggered **manually** via `workflow_dispatch`, accepting the image tag to deploy as an input (e.g. `pr-34`). No image is rebuilt — the exact artifact validated in CI is promoted to production. The workflow:

1. Authenticates to GCP using the `GCP_SA_KEY` service account.
2. Verifies that the requested image tag exists in Artifact Registry, failing early otherwise.
3. Renders `service.yaml` with `envsubst` (explicit variable allowlist), building the image URL from the input tag.
4. Deploys declaratively via `gcloud run services replace`.

### Roadmap: Full Automation

The current manual `workflow_dispatch` trigger is an intentional first step. A future iteration will automate the entire deployment flow — triggering the CD automatically on merge and introducing semantic versioning with automated GitHub tags and releases (driven by Conventional Commits). The manual deploy will then be superseded by version-based promotion, while the per-PR image tagging and declarative `gcloud run services replace` mechanics established here remain the foundation.

## 5. Declarative Service Manifest

The Cloud Run service is managed declaratively via a `service.yaml` file located at the root of the repository. This file is the single source of truth for the service configuration, including container resources, auto-scaling, ingress, and environment variables.

Sensitive variables (`GITHUB_TOKEN`, `JWT_SECRET`) are never hardcoded in the YAML. They are stored in GCP Secret Manager and injected directly into the container at runtime via `valueFrom: secretKeyRef`.

### Applying the manifest locally

Export the required environment variables and use `envsubst` to replace the placeholders before applying:

```bash
export IMAGE_URL="us-central1-docker.pkg.dev/jor-mcp/jor-mcp/jor-mcp-server:SHA"
export GCP_PROJECT_NUMBER="959918358302"
export FIREBASE_PROJECT_ID="..."
export WORDPRESS_API_URL="..."
export GH_REPOS="..."
export OTEL_EXPORTER_OTLP_ENDPOINT="..."

envsubst '${IMAGE_URL} ${GCP_PROJECT_NUMBER} ${FIREBASE_PROJECT_ID} ${WORDPRESS_API_URL} ${GH_REPOS} ${OTEL_EXPORTER_OTLP_ENDPOINT}' \
  < service.yaml | gcloud run services replace - --region us-central1
```

### In the CD pipeline (GitHub Actions)

The variables above are configured as repository **Variables** (`vars`) — except `IMAGE_URL`, which the workflow builds from the `image_tag` input. The `envsubst` step uses an explicit allowlist so only the intended placeholders are substituted, leaving any other `$` in the manifest untouched.