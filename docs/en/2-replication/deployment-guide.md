<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Infrastructure & Deployment Guide

This document outlines the deployment architecture for the Jor-MCP server on Google Cloud Platform (GCP).

---

## 1. GCP Architecture Overview

The system is designed to be fully serverless, highly available, and stateless at the application layer.

*   **Entrypoint:** Global External Application Load Balancer (Handles custom domains, SSL, and SSE streaming). [See detailed configuration guide](load-balancer-config.md).
*   **Frontend Hosting:** Google Cloud Storage (GCS) Bucket configured as a Backend Bucket on the Load Balancer, with Cloud CDN enabled.
*   **Compute:** Google Cloud Run (Containerized, auto-scaling). Locked down to "Internal and Cloud Load Balancing traffic only."
*   **Database/State:** Google Cloud Firestore (Handles distributed rate-limiting, OAuth DCR clients, and codes).
*   **Identity:** Google Cloud Identity Platform / Firebase Auth (Validates JWTs).
*   **Observability:** Google Cloud Operations Suite (Cloud Logging and Cloud Trace via OpenTelemetry).

---

## 2. Environment Variables & Resources

The server relies strictly on environment variables for configuration. No secrets are hardcoded. In GCP, these are injected securely via Google Secret Manager into Cloud Run.

For a comprehensive guide detailing every environment variable and resource configuration, please refer to the **[Configuration & Environment Guide](configuration-and-env.md)**.

> **Note on Routing:** Ensure your Global Load Balancer is configured to route traffic destined for `/mcp/*` and `/api/oauth/*` to the Serverless NEG (Cloud Run service), and all other traffic (`/*`) to the Backend Bucket (GCS).

---

## 3. Dockerization Strategy

We use a multi-stage `Dockerfile` to keep the production image secure and lightweight:

1.  **Builder Stage:** Uses the `uv` package manager to resolve and install dependencies into an isolated virtual environment (`.venv`).
2.  **Runtime Stage:** Copies only the `.venv` and the `src/` directory into a slim Python base image. It runs the application as a non-root user (`appuser`) to comply with container security best practices.

---

## 4. Automating Deployment with GitHub Actions (Replication)

If your organization is replicating `jor-mcp` using a fork or a cloned repository, you can utilize the included GitHub Actions workflows (`.github/workflows/`) to automate building your Docker images and deploying them to Google Cloud Run.

### 4.1 Configuring Repository Secrets
To enable the deployment workflows in your repository, navigate to **Settings > Secrets and variables > Actions** in your GitHub repository and define the following secrets:

| Secret Name | Description | Example / Resource |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | JSON key of a GCP Service Account with permissions to write to Artifact Registry and deploy to Cloud Run. | *(Required)* |
| `GCP_PROJECT_ID` | Your Google Cloud project ID. | `my-mcp-project-123` |
| `GCP_PROJECT_NUMBER` | Your Google Cloud project number (used in the Knative service annotations). | `959918358302` |

### 4.2 Available Workflows
Our repository contains pre-configured workflows that you can adapt:
*   **`ci.yml`**: Compiles, runs tests, performs security scans, and builds/pushes the container to your own Google Artifact Registry.
*   **`cd.yml`**: Triggers a manual deployment flow via GitHub's `workflow_dispatch` (allowing you to select exactly which image tag to deploy to Cloud Run without auto-deploying every merge).

For detailed documentation on the internal testing gates, versioning mechanisms, and detailed pipeline jobs, please refer to the **[Contributing Guide](../../../CONTRIBUTING.md#continuous-integration-ci)**.

---

## 5. Declarative Service Manifest

The Cloud Run service is managed declaratively via a `service.yaml` file located at the root of the repository. This file is the single source of truth for the service configuration, including container resources, auto-scaling, ingress, and environment variables.

Sensitive variables are never hardcoded in the YAML. They are stored in GCP Secret Manager and injected directly into the container at runtime via `valueFrom: secretKeyRef`.

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
