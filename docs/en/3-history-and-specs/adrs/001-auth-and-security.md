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

1.  **Authentication:** The project adopts the **OAuth 2.1 (Resource Server + Proxy)** model. We utilize **Firebase Auth / Google Identity Platform** as the Identity Provider. To address MCP client quirks (such as localhost/127.0.0.1 mismatches and DCR compliance), the Python backend acts as an **OAuth Defensive Proxy**, normalizing DCR and Token Exchange requests before interacting with Firebase to issue short-lived Access Tokens and long-lived Refresh Tokens.
2.  **Rate Limiting:** Mandatory abuse prevention. We pivoted from **GCP Memorystore (Redis)** to **Google Cloud Firestore** to eliminate base-provisioning costs and maintain a fully serverless architecture.
3.  **Persistence (Session Management):** By implementing standard OAuth 2.1 Refresh Tokens, we ensure a "Login Once" experience for journalists in Claude Desktop. Claude Desktop automatically manages token renewal in the background, keeping the authentication persistent for weeks without user intervention.
4.  **Authorization (Tiers):** The Firestore rate limiter reads `tier` claims from the Firebase-issued JWTs to apply differentiated traffic quotas (Basic vs. Pro).