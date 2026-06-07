# Pre-POC Spike: Authentication and Security

## 1. Objective
To determine the optimal strategy for authenticating LLM clients and securing the Jor-MCP server.

## 2. Context
The Jor-MCP server will be exposed publicly (via Cloud Run or a Load Balancer) to serve content to various AI agents. It requires a mechanism to verify the identity of the requesting client and enforce usage limits to prevent abuse and manage costs.

## 3. Evaluated Authentication Strategies

### 3.1 API Keys (Symmetric)
*   **Concept:** The server and the client share a secret string.
*   **Pros:** Extremely simple to implement.
*   **Cons:** Hard to manage rotation; if compromised, all access is breached. Doesn't easily scale to multi-tenant B2C scenarios.

### 3.2 JSON Web Tokens (JWT) - Symmetric (HS256)
*   **Concept:** The server generates and signs a token using a secret key. The client passes this token in the `Authorization: Bearer` header.
*   **Pros:** Stateless; can encode basic claims (expiration, user ID).
*   **Cons:** Requires the Jor-MCP server to manage user logins and secret distribution.

### 3.3 OAuth 2.0 Resource Server (Asymmetric - RS256/JWKS)
*   **Concept:** A dedicated Identity Provider (IdP) like Firebase Auth, Auth0, or Clerk handles user registration and login. It issues a JWT signed with a private key. The Jor-MCP server fetches the IdP's public keys (JWKS) to verify the token signature.
*   **Pros:** Completely decouples authentication logic from the MCP server. Highly scalable. Native support for frontend web clients.
*   **Cons:** Slight increase in initial setup complexity.

## 4. Architectural Decision: Security & Auth

1.  **Authentication:** The project will adopt the **OAuth 2.0 Resource Server** model. Specifically, it will use **Firebase Auth / Google Identity Platform**. This aligns with the GCP ecosystem, is cost-effective, and allows the Python server to easily validate tokens using the `firebase-admin` SDK without managing passwords or user databases.
2.  **Rate Limiting:** To prevent abuse, rate limiting is mandatory. Because the Cloud Run deployment will be stateless and horizontally scalable, an in-memory rate limiter is insufficient. We initially considered GCP Memorystore (Redis) to implement a distributed sliding-window rate limit, but pivoted to **Google Cloud Firestore** to eliminate base-provisioning costs, maintaining a fully serverless, pay-per-operation architecture suitable for low budgets.
3.  **Authorization (Tiers):** By utilizing Firebase Auth, we can inject custom claims into the JWT (e.g., `tier: basic` or `tier: pro`). The Firestore rate limiter will read these claims to apply differentiated traffic quotas.