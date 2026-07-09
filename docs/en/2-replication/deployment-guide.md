<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Infrastructure & Deployment Guide

This document outlines the deployment architecture for the Jor-MCP server on Google Cloud Platform (GCP), GCP service account permissions, Firebase Authentication console security settings, and Firestore allow-list management.

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

## 2. GCP IAM Service Account Permissions

To run `jor-mcp` securely, you should create a dedicated Google Cloud Service Account for the Cloud Run service. Running the service as the Default Compute Service Account with broad "Editor" permissions is strongly discouraged in production.

### Required IAM Roles
Assign the following granular roles to the Cloud Run service account:

1.  **Cloud Datastore User (`roles/datastore.user`):** Required to allow the application to read and write rate-limit entries, OAuth clients, and temporary codes in Firestore.
2.  **Secret Manager Secret Accessor (`roles/secretmanager.secretAccessor`):** Required to inject sensitive environment variables (such as `FIREBASE_WEB_API_KEY` and `MCP_GITHUB_TOKEN`) directly into the container at startup.
3.  **Cloud Trace Agent (`roles/cloudtrace.agent`):** Required to allow OpenTelemetry auto-instrumentation to send latency trace spans back to GCP Cloud Trace.
4.  **Logs Writer (`roles/logging.logWriter`):** Required to send application logs directly to GCP Cloud Logging.
5.  **Monitoring Metric Writer (`roles/monitoring.metricWriter`):** Required to export standard service metrics to Cloud Monitoring.
6.  **Storage Object Viewer (`roles/storage.objectViewer`):** Optional, but required if the server needs to read additional assets or configurations from private GCS buckets.

---

## 3. Firebase Console Security & Authentication Configuration

Because the Jor-MCP consent flow utilizes Google SSO to verify user identities, you must configure your Firebase / Google Cloud Identity Platform console to prevent unauthorized registrations.

### 3.1 Disabling Self-Registration
By default, anyone with a Google account can sign in to your Firebase app, creating an account. You must disable self-signup to secure the system:
1.  Go to the **Firebase Console** and select your project.
2.  Navigate to **Authentication > Settings > User actions**.
3.  Uncheck the option **"Enable create (sign-up)"** (or **"Permitir criação de contas"**).
4.  Save your changes. This ensures only accounts pre-provisioned or matching existing records can be authenticated, although Google SSO will still act as a secure authenticator for valid, existing identities.

### 3.2 Disable Email & Password Sign-In
To prevent attackers from attempting credential stuffing attacks or bypassing Google SSO:
1.  In the **Firebase Console**, go to **Authentication > Sign-in method**.
2.  Select **Email/Password** and click **Disable** (or turn off the status toggle).
3.  Ensure **Google** is the only enabled sign-in provider.

---

## 4. Understanding the Non-Secret Nature of Firebase Configurations

It is a common misconception that the `firebaseConfig` object (containing `apiKey`, `authDomain`, `projectId`, etc.) must be kept strictly secret. 

### Why the API Key is Public
In Firebase, the `apiKey` acts as a public **project identifier** rather than a master secret key. It is embedded directly in client-side code (the web portal) so that the browser can connect to Google APIs. Because it is public by design, you cannot protect your database by hiding it.

### How to Protect Your System
Security **must not** rely on hiding the `apiKey`. Instead, protect your system via:
1.  **GCP API Restrictions:** Go to the Google Cloud Console, navigate to **APIs & Services > Credentials**, find your Firebase API Key, and restrict its usage to your official web portal domain (e.g., `https://jormcp.ambiental.media`).
2.  **Firestore Security Rules:** Ensure your NoSQL database is locked down so that clients can only read/write their permitted directories. For example, deny general write access to the `allowed_users` or `oauth_clients` collections.

---

## 5. Manual Allow-list Management (`allowed_users`)

Jor-MCP enforces access control using an explicit allow-list stored in Firestore. 

To authorize a new journalist or partner to use the MCP server, an administrator must manually add their email to the `allowed_users` collection in Firestore.

### 5.1 Allow-list Document Format
Add a document under the `allowed_users` collection with the following specifications:
*   **Document ID:** Must be the user's Google email address in **lowercase** (e.g., `user@domain.com`). This ensures lookups are case-insensitive.
*   **Document Fields:**
    *   `status` (String): Must be set to `"active"` to permit access. If set to `"disabled"` or any other value, authorization will be rejected.
    *   `tier` (String, Optional): Can be `"basic"` or `"pro"`. Dictates the monthly request/token limit applied to this user. Defaults to `"basic"` if omitted.

---

## 6. Environment Variables & Resources

The server relies strictly on environment variables for configuration. No secrets are hardcoded. In GCP, these are injected securely via Google Secret Manager into Cloud Run.

For a comprehensive guide detailing every environment variable and resource configuration, please refer to the **[Configuration & Environment Guide](configuration-and-env.md)**.

> **Note on Routing:** Ensure your Global Load Balancer is configured to route traffic destined for `/mcp/*` and `/api/oauth/*` to the Serverless NEG (Cloud Run service), and all other traffic (`/*`) to the Backend Bucket (GCS).

---

## 7. Dockerization Strategy

We use a multi-stage `Dockerfile` to keep the production image secure and lightweight:

1.  **Builder Stage:** Uses the `uv` package manager to resolve and install dependencies into an isolated virtual environment (`.venv`).
2.  **Runtime Stage:** Copies only the `.venv` and the `src/` directory into a slim Python base image. It runs the application as a non-root user (`appuser`) to comply with container security best practices.

---

## 8. Automating Deployment with GitHub Actions (Replication)

If your organization is replicating `jor-mcp` using a fork or a cloned repository, you can utilize the included GitHub Actions workflows (`.github/workflows/`) to automate building your Docker images and deploying them to Google Cloud Run.

### 8.1 Configuring Repository Secrets
To enable the deployment workflows in your repository, navigate to **Settings > Secrets and variables > Actions** in your GitHub repository and define the following secrets:

| Secret Name | Description | Example / Resource |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | JSON key of a GCP Service Account with permissions to write to Artifact Registry and deploy to Cloud Run. | *(Required)* |
| `GCP_PROJECT_ID` | Your Google Cloud project ID. | `my-mcp-project-123` |
| `GCP_PROJECT_NUMBER` | Your Google Cloud project number (used in the Knative service annotations). | `959918358302` |

### 8.2 Available Workflows
Our repository contains pre-configured workflows that you can adapt:
*   **`ci.yml`**: Compiles, runs tests, performs security scans, and builds/pushes the container to your own Google Artifact Registry.
*   **`cd.yml`**: Triggers a manual deployment flow via GitHub's `workflow_dispatch` (allowing you to select exactly which image tag to deploy to Cloud Run without auto-deploying every merge).

For detailed documentation on the internal testing gates, versioning mechanisms, and detailed pipeline jobs, please refer to the **[Contributing Guide](../../../CONTRIBUTING.md#continuous-integration-ci)**.

---

## 9. Declarative Service Manifest

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
