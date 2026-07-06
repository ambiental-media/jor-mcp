<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# ADR 006: Native MCP OAuth 2.1 Implementation Strategy

## 1. The "Why" (Context)
*   **Goal:** Provide a "zero-configuration" login experience for non-technical journalists using Claude Desktop.
*   **Problem:** Claude Desktop does not support interactive browser logins natively unless the server implements the strict MCP OAuth 2.1 protocol (PKCE + Dynamic Client Registration).
*   **Solution:** We are shifting from simple, static API keys / JWTs to a full Native MCP OAuth 2.1 flow using a "Defensive Proxy" pattern.

## 2. What Changed in the Architecture?
*   **Old Architecture:** `jor-mcp` (Python) was a simple Resource Server that just validated Firebase JWTs.
*   **New Architecture (Multi-Repo):** 
    *   `jor-mcp` (Python Backend): Now acts as an **OAuth Proxy**. It intercepts OAuth requests from Claude, normalizes them, and talks to Firebase to mint tokens.
    *   `jor-mcp-site` (Next.js Frontend): Now acts as the **Consent Portal**. It handles the actual user login and the "Allow Claude Access" screen.

## 3. How the New Flow Works (Quick Summary)
1.  **Discovery:** Claude hits `jor-mcp` and is told where to authenticate.
2.  **Registration (DCR):** Claude registers itself with `jor-mcp`.
3.  **Consent:** Claude opens the user's browser to `jor-mcp-site/authorize`. The user logs in via Firebase and clicks "Allow".
4.  **Exchange:** The browser redirects back to Claude with a code. Claude trades that code with `jor-mcp` for long-lived Firebase tokens.

## 4. How We Will Implement It (Engineering Tasks)

### Backend Team (`jor-mcp` - Python)
*   **Endpoints to Build:** 
    *   `/.well-known/oauth-authorization-server` (Metadata)
    *   `/api/oauth/register` (Dynamic Client Registration)
    *   `/api/oauth/token` (Token Exchange & PKCE validation)
*   **Critical Quirks to Handle:**
    *   *Loopback Normalization:* Must forcefully normalize `localhost` vs `127.0.0.1` mismatches from Claude.
    *   *Public Client Forcing:* Must force `token_endpoint_auth_method` to `"none"`.

### Frontend Team (`jor-mcp-site` - Next.js)
*   **Pages to Build:**
    *   `/authorize`: The UI that catches the `client_id` and `code_challenge`, forces Firebase login, and POSTs to the Python backend to get an auth code.
    *   `/admin`: B2B dashboard for Ambiental Media staff to upgrade users in Firestore from `tier: basic` to `tier: pro`.

### Database (Firestore)
*   Add new collections: `oauth_clients` (to store registered Claude instances) and `oauth_codes` (to store temporary PKCE challenges).
