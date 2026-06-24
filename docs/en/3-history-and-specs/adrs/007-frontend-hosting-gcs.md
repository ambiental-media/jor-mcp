# ADR 007: Frontend Hosting Strategy (GCS Bucket)

## 1. Context
The Jor-MCP project requires hosting the `jor-mcp-site` (Next.js) landing page and the interactive OAuth 2.1 consent UI (`/authorize`) on the same custom domain (`jormcp.ambiental.media`) as the Python FastMCP backend API. We utilize a Google Cloud Global External Application Load Balancer as the primary entry point to handle TLS and URL routing.

## 2. Alternatives Considered

### 2.1 Internet NEG to Legacy Provider (Hostinger)
*   **Approach:** Route the `/*` traffic from the GCP Load Balancer to an external Hostinger server where the legacy landing page resides, and route `/mcp/*` to Cloud Run.
*   **Rejected because:** 
    *   *TLS/SNI Mismatch:* Proxying HTTPS traffic to shared hosting environments often fails due to Server Name Indication (SNI) and certificate mismatches.
    *   *FinOps Violation:* We would be charged premium egress bandwidth by GCP just to proxy static HTML from Hostinger back to the user.
    *   *Reliability:* Introduces cross-provider points of failure.

### 2.2 Cloud Run (Node.js)
*   **Approach:** Deploy the Next.js application as a dynamic Node.js container on Cloud Run alongside the Python server.
*   **Rejected because:** The landing page and the OAuth consent UI (`/authorize`) can be compiled to pure static HTML/JS/CSS using Next.js `output: 'export'`. Running a compute instance for static assets violates FinOps efficiency principles.

## 3. Decision
We will host the static Next.js export (`out/` directory) in a **Google Cloud Storage (GCS) Bucket** configured as a Backend Bucket on the existing Global Load Balancer, and we will enable **Cloud CDN**.

## 4. Consequences
*   **Cost:** Near-zero hosting costs (pennies per month for storage and CDN caching), maximizing FinOps efficiency.
*   **Reliability:** 99.999% availability for the frontend UI, completely decoupled from the Python compute instances.
*   **CI/CD:** The deployment pipeline must be updated to include a step that uploads the static assets to the GCS bucket (`gsutil rsync` or an equivalent GitHub Action) rather than relying on standard container deployments.
*   **CORS:** The static frontend will make client-side AJAX calls to the Python backend (e.g., `POST /api/oauth/approve`), requiring the backend to strictly configure Cross-Origin Resource Sharing (CORS).