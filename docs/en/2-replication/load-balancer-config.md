<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Global Load Balancer Configuration

## 1. Overview
The Global External Application Load Balancer acts as the single entry point for `jormcp.ambiental.media`. It serves two critical functions:
1.  **SSL/TLS Termination:** Manages the Google-managed SSL certificate.
2.  **Path-Based Routing:** Splits traffic between the Python API (Cloud Run) and the Next.js Frontend (Cloud Storage).

*Note: These instructions assume manual provisioning via the Google Cloud Console.*

## 2. Backend Services Configuration
To route traffic correctly, you must create two distinct Backend Services in GCP.

### 2.1 Backend Service: API (Serverless NEG)
*   **Type:** Serverless Network Endpoint Group (NEG).
*   **Target:** The `jor-mcp` Cloud Run service.
*   **Protocol:** HTTP/2 (Recommended for SSE streaming).
*   **Timeout:** Ensure the backend timeout is set high enough (e.g., 3600 seconds) so that Server-Sent Events (SSE) connections do not drop prematurely.

### 2.2 Backend Bucket: Frontend (GCS)
*   **Type:** Backend Bucket.
*   **Target:** The GCS bucket containing the Next.js static export (`gs://your-bucket-name`).
*   **Cloud CDN:** Enable Cloud CDN on this backend bucket to cache static assets globally.

## 3. URL Map (Routing Rules)
The core of the load balancer is the URL Map. Configure the Host and Path rules as follows:

| Host | Path | Backend |
| :--- | :--- | :--- |
| `jormcp.ambiental.media` | `/mcp/*` | API (Serverless NEG) |
| `jormcp.ambiental.media` | `/api/oauth/*` | API (Serverless NEG) |
| `jormcp.ambiental.media` | `/.well-known/*` | API (Serverless NEG) |
| `jormcp.ambiental.media` | `/*` (Default) | Frontend (Backend Bucket) |

## 4. Security Policies & CORS
*   **CORS:** Ensure that the Load Balancer is configured to allow `OPTIONS` preflight requests to reach the Cloud Run service, so the Python backend can respond with the correct `Access-Control-Allow-Origin` headers for the `/api/oauth/approve` endpoint.
*   **Cloud Armor (Optional / Advanced):** You may attach a Google Cloud Armor WAF policy to the API Backend Service to block malicious IPs before they hit Cloud Run. 
    *   *FinOps Warning:* Unlike Cloud Run and Firestore which scale to zero, Cloud Armor introduces fixed monthly costs (approximately $5-$10/month base fee). Because Jor-MCP includes application-level rate limiting via Firestore, Cloud Armor is only necessary if you expect severe volumetric DDoS attacks.