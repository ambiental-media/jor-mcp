# Infrastructure & Deployment

This document outlines the deployment architecture for the Jor-MCP server on Google Cloud Platform (GCP).

## 1. GCP Architecture Overview

The system is designed to be fully serverless, highly available, and stateless at the application layer.

- **Entrypoint:** Global External Application Load Balancer (Handles custom domains, SSL, and SSE streaming). [See detailed configuration guide](load-balancer-config.md).
- **Frontend Hosting:** Google Cloud Storage (GCS) Bucket configured as a Backend Bucket on the Load Balancer, with Cloud CDN enabled.
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
> 
> **Note on Routing:** Ensure your Global Load Balancer is configured to route traffic destined for `/mcp/*` and `/api/oauth/*` to the Serverless NEG (Cloud Run service), and all other traffic (`/*`) to the Backend Bucket (GCS).

## 3. Dockerization Strategy

We use a multi-stage `Dockerfile` to keep the production image secure and lightweight.

1. **Builder Stage:** Uses the `uv` package manager to resolve and install dependencies into an isolated virtual environment (`.venv`).
2. **Runtime Stage:** Copies only the `.venv` and the `src/` directory into a slim Python base image. It runs the application as a non-root user (`appuser`) to comply with container security best practices.

## 4. CI/CD Pipeline

The project uses three separate GitHub Actions workflows. Continuous Integration and release/versioning are fully automated; deployment to Cloud Run is a deliberate manual step.

### 4.1 Continuous Integration — `.github/workflows/ci.yml`

Triggered on every Pull Request. It has three independent jobs:

1. **`check`** — Code quality and security gate. Runs lint (`ruff check`), format check (`ruff format --check`), type check (`mypy`), tests with 90% coverage enforcement (`pytest --cov-fail-under=90`), SAST (`bandit`), and dependency audit (`pip-audit`).
2. **`build-and-push`** — Runs only after `check` passes. Builds the Docker image, scans it with Trivy (fails on `CRITICAL` and `HIGH` library vulnerabilities), and pushes it to Artifact Registry tagged `:pr-<PR_NUMBER>` (e.g. `:pr-44`).
3. **`commitlint`** — Verifies that at least one commit in the PR follows the Conventional Commits format. This is what feeds the automated versioning at release time.

### 4.2 Release & Versioning — `.github/workflows/release.yml`

Triggered when a Pull Request is **merged into `main`**. It runs [`python-semantic-release`](https://python-semantic-release.readthedocs.io/), which:

1. Parses the Conventional Commits in the merged PR and computes the next [SemVer](https://semver.org/) version (`fix` → PATCH, `feat` → MINOR, `BREAKING CHANGE` → MAJOR).
2. Bumps the `version` field in `pyproject.toml`, creates and pushes the `vX.Y.Z` git tag, and publishes a GitHub Release with auto-generated notes.
3. If (and only if) a release was produced, **retags the existing image** — the `:pr-<N>` image built during CI is retagged in Artifact Registry to `:vX.Y.Z` and `:latest`. No rebuild happens; the same digest is promoted.

This means a merged PR never rebuilds the image — the artifact tested in CI is the exact one promoted to a versioned release.

### 4.3 Continuous Deployment — `.github/workflows/cd.yml`

Deployment is **manual and intentional**, not triggered by merges. It runs via `workflow_dispatch` with a required `image_tag` input (e.g. `pr-44` or `v1.2.0`). The workflow:

1. Verifies the requested tag actually exists in Artifact Registry (fails fast otherwise).
2. Renders `service.yaml` with `envsubst`, substituting only an explicit allowlist of variables.
3. Deploys the selected image to Cloud Run via `gcloud run services replace`.

Because deployment consumes an existing image by tag, it is fully decoupled from versioning: you choose exactly which build reaches production, and the deploy step never changes the project version.

## 5. Declarative Service Manifest

The Cloud Run service is managed declaratively via a `service.yaml` file located at the root of the repository. This file is the single source of truth for the service configuration, including container resources, auto-scaling, ingress, and environment variables.

Sensitive variables (for example `MCP_GITHUB_TOKEN`) are never hardcoded in the YAML. They are stored in GCP Secret Manager and injected directly into the container at runtime via `valueFrom: secretKeyRef`.

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