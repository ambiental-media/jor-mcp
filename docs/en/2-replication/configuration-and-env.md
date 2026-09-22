<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Configuration & Environment Variables

This document provides a comprehensive list of all environment variables and cloud resources utilized by the Jor-MCP server. If you are replicating the server for your own newsroom, use this guide to configure your `.env` files and Google Cloud service settings.

---

## 1. Major Cloud Resources Utilized

Jor-MCP is designed as a fully serverless platform on **Google Cloud Platform (GCP)**. The following primary resources must be configured:

1.  **Google Cloud Run:** Hosts the stateless, containerized Python `jor-mcp` ASGI server.
2.  **Google Cloud Storage (GCS):** Hosts the static web portal assets for the Next.js consent portal (`jor-mcp-site`).
3.  **Google Cloud Firestore:** A NoSQL document database used in Datastore mode. It stores monthly rate limits, dynamically registered OAuth clients (DCR), and short-lived authorization codes.
4.  **Google Cloud Identity Platform / Firebase Auth:** Handles Google SSO authentication and mints secure JSON Web Tokens (JWTs).
5.  **External WordPress REST API:** The target CMS site where editorial articles are published.
6.  **External GitHub REST API:** Target repository hosting multilingual editorial metadata in JSON files.

---

## 2. Environment Variables Reference

Configure these variables in your Cloud Run service environment settings or local `.env` files.

### 2.1 State & Rate Limiting (Firestore)
*   `FIRESTORE_DATABASE_ID` (Default: `"(default)"`): The Firestore database ID. Override if utilizing a named database instance.
*   `RATE_LIMIT_COLLECTION` (Default: `"rate_limits"`): Firestore collection containing monthly user counter windows.
*   `RATE_LIMIT_BASIC_REQUESTS` (Default: `"500"`): Monthly quota for `basic` tier users.
*   `RATE_LIMIT_PRO_REQUESTS` (Default: `"2000"`): Monthly quota for `pro` tier users.

#### Per-IP limit on unauthenticated routes
Applies only to the auth-exempt surface (`/.well-known/*` and `/api/oauth/*`), which would
otherwise let anyone flood Firestore through `POST /api/oauth/register`.

*   `IP_RATE_LIMIT_COLLECTION` (Default: `"ip_rate_limits"`): Firestore collection holding the short per-IP fixed windows. Documents carry an `expires_at` field — configure a Firestore TTL policy on it so expired windows are reclaimed automatically.
*   `IP_RATE_LIMIT_REQUESTS` (Default: `"60"`): Requests allowed per IP per window.
*   `IP_RATE_LIMIT_WINDOW_SECONDS` (Default: `"60"`): Window length in seconds.
*   `IP_RATE_LIMIT_TRUSTED_PROXIES` (Default: `"1"`): How many proxies append to `X-Forwarded-For` at the right end. Google Cloud Load Balancing rewrites the header as `<supplied-value>, <client-ip>, <load-balancer-ip>`, so the client IP is read that many positions from the right — reading the left-most entry instead would let any caller spoof its identity. Set to `"0"` when the container is reached directly.

### 2.2 Security & OAuth 2.1 Proxy
*   `CORS_ALLOWED_ORIGINS` (Default: `"http://localhost:3000,https://jormcp.ambiental.media"`): Comma-separated list of origins allowed to call the server.
*   `OAUTH_SERVER_BASE_URL` (Default: `"https://jormcp.ambiental.media"`): Public URL of this server. Used for discovery metadata.
*   `OAUTH_PORTAL_BASE_URL` (Default: `"https://jormcp.ambiental.media"`): Public URL of the Next.js portal.
*   `OAUTH_CLIENTS_COLLECTION` (Default: `"oauth_clients"`): Firestore collection storing registered clients.
*   `OAUTH_CODES_COLLECTION` (Default: `"oauth_codes"`): Firestore collection storing temporary OAuth codes and PKCE state.
*   `OAUTH_CODE_TTL_SECONDS` (Default: `"600"`): Lifetime of issued authorization codes.
*   `ALLOWED_USERS_COLLECTION` (Default: `"allowed_users"`): Firestore whitelist collection of user emails.
*   `FIREBASE_WEB_API_KEY` (Required in production): The Web API Key found in your Firebase project settings, used for secure token exchange.

### 2.3 External Content Source Configurations
*   `WORDPRESS_API_URL` (Default: `"https://ambiental.media/wp-json"`): Base URL of the target WordPress CMS API.
*   `MCP_GITHUB_TOKEN` (Optional for public repos, recommended): Personal Access Token to authenticate against GitHub API.
*   `MCP_GITHUB_REPOS` (Required): Comma-separated list of target GitHub repositories to search (in `owner/repo` format).
*   `MCP_GITHUB_API_BASE_URL` (Default: `"https://api.github.com"`): Base API endpoint for GitHub REST calls.

### 2.4 Diagnostics & Telemetry
*   `HTTP_TIMEOUT` (Default: `"10.0"`): Outbound HTTP request timeout in seconds.
*   `LOG_LEVEL` (Default: `"INFO"`): Minimum level of the root logger.
*   `OTEL_TRACES_EXPORTER` (Default: `"none"`): Span exporter — `otlp`, `console` or `none`. Export is opt-in: setting `OTEL_EXPORTER_OTLP_ENDPOINT` alone changes nothing, this variable must be set to `otlp` as well. An endpoint that refuses connections makes every batch retry and fail, flooding the log with transient errors, so silence is the default. Spans are still created either way — that is where the `trace_id` on each log record comes from.
*   `OTEL_EXPORTER_OTLP_ENDPOINT` (Optional): Collector endpoint used when `OTEL_TRACES_EXPORTER=otlp`.
*   `OTEL_SERVICE_NAME` (Default: `"jor-mcp"`): Registered service name in spans.
*   `GCP_PROJECT_ID` (Optional on Cloud Run, required elsewhere): GCP Project ID used to link log entries with Cloud Logging traces. On Cloud Run it is read from the ambient credentials when unset. Anywhere else it must be provided, otherwise the trace correlation fields are omitted from every log entry.

---

## 3. Note on Replicating the Infrastructure (Future Playbook)

Currently, the GCP infrastructure resources (Load Balancers, Cloud Run, Firestore collections, and Identity Platform) are manually provisioned.

**Planned Update:** After the initial pilot replication phase is finalized, we will deliver a **comprehensive replication playbook**. This will include:
*   **Infrastructure as Code (IaC):** Terraform scripts to provision all required GCP resources automatically.
*   **Configuration as Code (CaC):** Automated configurations to securely hook up Identity Platform, Firestore rules, and secrets deployment.
