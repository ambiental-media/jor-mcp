<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# API & Tool Contracts

## Base URL & Routing
The Jor-MCP server exposes its Model Context Protocol (MCP) interface exclusively on the `/mcp` route. All SSE (Server-Sent Events) connections and JSON-RPC message exchanges must be directed to endpoints prefixed with this route.

*   **SSE Endpoint:** `GET /mcp/sse`
*   **Message Endpoint:** `POST /mcp/messages` (Inferred via the SSE connection handshake)
*   **Health Check:** `GET /health` (Bypasses authentication and rate limiting)

---
(Note: While this documentation is in English, the `description` fields injected into the `@mcp.tool()` decorators in the Python codebase must be written in Portuguese to provide localized context to the LLMs.)

## 1. `search_content`

**Purpose:** Unified full-text search across all Ambiental Media properties (WordPress sites and Next.js microsites).

### Request Parameters
| Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | **Yes** | - | The keyword or phrase to search for. |
| `source` | `string` | No | `"all"` | Filter by source. Allowed values: `"all"`, `"wordpress"`, `"nextjs"`. |

### Response Schema (Array of Objects)
```json
[
  {
    "id": "1234 (WP ID) or github-path",
    "title": "Article or Section Title",
    "excerpt": "Short summary or text snippet...",
    "date": "2023-10-25T10:00:00Z",
    "link": "https://ambiental.media/full-url",
    "source": "wordpress | nextjs:mata-nativa"
  }
]
```
*Note: If no results are found, the tool throws a `ToolError` with a semantic hint for the LLM to try different keywords.*

---

## 2. `get_full_article`

**Purpose:** Retrieves the complete, cleaned text of a specific WordPress article or project. It strips HTML tags, shortcodes, and layout artifacts.

### Request Parameters
| Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `url_or_id` | `string` | **Yes** | - | The numeric WordPress ID or the full URL of the article. |

### Response Schema (Object)
```json
{
  "title": "Full Article Title",
  "date": "2023-10-25T10:00:00Z",
  "link": "https://ambiental.media/full-url",
  "content": "The fully cleaned, plain-text body of the article ready for LLM summarization or analysis..."
}
```

---

## 3. `list_latest_news`

**Purpose:** Returns the most recent publications. Useful for providing the agent with temporal context about what is currently happening.

### Request Parameters
| Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `integer`| No | `5` | Number of recent articles to return (Max: 20). |

### Response Schema (Array of Objects)
*(Follows the exact same schema as `search_content` without the `source` field, as it only queries the main WordPress publication).*
```json
[
  {
    "id": "1234",
    "title": "Recent Article Title",
    "excerpt": "Short summary...",
    "date": "2023-10-25T10:00:00Z",
    "link": "https://ambiental.media/full-url"
  }
]
```

## 4. OAuth 2.1 Proxy Endpoints (Internal API)

These endpoints are used internally to facilitate the Native MCP OAuth 2.1 flow between Claude Desktop, the `jor-mcp-site` Next.js portal, and the `jor-mcp` backend.

### Consistent Error Semantics
All OAuth endpoints follow this standard error schema for non-2xx responses:
```json
{
  "error": "invalid_request",
  "error_description": "Human readable details (e.g., PKCE verification failed)"
}
```

### CORS Policy
All `/api/oauth/*` routes are served behind a CORS middleware so the browser-based
consent portal (`jor-mcp-site`) can call them via AJAX. They also bypass Firebase
authentication and rate limiting — they are the mechanism through which clients
obtain Firebase tokens in the first place.

*   **Allowed Origins:** configured via the `CORS_ALLOWED_ORIGINS` environment
    variable (comma-separated). Defaults to `http://localhost:3000` (dev portal)
    and `https://jormcp.ambiental.media` (prod portal).
*   **Allowed Methods:** `GET`, `POST`, `OPTIONS`.
*   **Allowed Headers:** `Authorization`, `Content-Type`.

### Base URLs
The absolute URLs advertised by the discovery metadata are built from two
environment variables (so dev and prod can diverge):

*   `OAUTH_SERVER_BASE_URL` — this backend / issuer (token + registration
    endpoints). Default `https://jormcp.ambiental.media`.
*   `OAUTH_PORTAL_BASE_URL` — the Next.js consent portal (`authorization_endpoint`).
    Default `https://jormcp.ambiental.media`.

---

### 4.0 Router Health
**Endpoint:** `GET /api/oauth/health`
**Purpose:** Liveness probe for the OAuth proxy router. Requires no authentication.

**Response Schema (200 OK):**
```json
{
  "status": "ok",
  "service": "jor-mcp-oauth"
}
```

---

### 4.0.1 Discovery Metadata
**Endpoints:**
*   `GET /.well-known/oauth-authorization-server` (RFC 8414)
*   `GET /.well-known/oauth-protected-resource` (RFC 9728)

**Purpose:** Let MCP clients (e.g. Claude Desktop) discover where to register and
authenticate. No authentication required. Served by the Python backend, so the
load balancer must route `/.well-known/*` to the backend NEG.

**`oauth-authorization-server` Response (200 OK):**
```json
{
  "issuer": "https://jormcp.ambiental.media",
  "authorization_endpoint": "https://jormcp.ambiental.media/authorize",
  "token_endpoint": "https://jormcp.ambiental.media/api/oauth/token",
  "registration_endpoint": "https://jormcp.ambiental.media/api/oauth/register",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "code_challenge_methods_supported": ["S256"],
  "token_endpoint_auth_methods_supported": ["none"]
}
```

**`oauth-protected-resource` Response (200 OK):**
```json
{
  "resource": "https://jormcp.ambiental.media/mcp",
  "authorization_servers": ["https://jormcp.ambiental.media"]
}
```

---

### 4.1 Dynamic Client Registration (DCR)
**Endpoint:** `POST /api/oauth/register`
**Purpose:** Called by Claude Desktop to register itself and obtain a `client_id`.

**Server-side behavior:**
*   `redirect_uris` is required (non-empty); unknown client metadata fields are ignored.
*   **Force public client:** `token_endpoint_auth_method` is always overwritten to `"none"`.
*   **Loopback normalization:** any `127.0.0.1` host in `redirect_uris` is rewritten to `localhost`.
*   A `client_id` (UUID) is generated and the client persisted to the `oauth_clients` Firestore collection.
*   Invalid JSON returns `400 invalid_request`; invalid metadata returns `400 invalid_client_metadata`.

**Request Schema:**
```json
{
  "client_name": "string",
  "redirect_uris": ["string"],
  "token_endpoint_auth_method": "none"
}
```

**Response Schema (201 Created):**
```json
{
  "client_id": "uuid-string",
  "client_name": "string",
  "redirect_uris": ["string"],
  "token_endpoint_auth_method": "none"
}
```

---

### 4.2 Consent Approval
**Endpoint:** `POST /api/oauth/approve`
**Purpose:** Called by the `jor-mcp-site` (Next.js) after the user clicks "Allow". Requires CORS.

**Server-side behavior:**
*   **Authentication:** requires `Authorization: Bearer <Firebase_ID_Token>`, verified via `firebase-admin`. Missing/invalid token returns `401 invalid_token`.
*   `client_id` and `code_challenge` are required; only `code_challenge_method = "S256"` is accepted.
*   The `client_id` must exist in `oauth_clients`, otherwise `400 invalid_client`.
*   `redirect_uri` is optional: when present it is loopback-normalized and must match a registered URI (else `400 invalid_request`); when absent the client's first registered URI is used.
*   **Allow-list:** the user's email (from the JWT) must exist in the `allowed_users` collection with `status == "active"`. A valid token whose email is missing/not whitelisted/not active returns `403 access_denied`. The list is curated manually by Ambiental Media (e.g. Firebase console); access is Google-SSO only.
*   A random `authorization_code` is generated and stored in `oauth_codes` together with the `code_challenge`, `uid`, `redirect_uri` and a short expiry (`OAUTH_CODE_TTL_SECONDS`, default 600s).

**Request Schema:**
*(Requires `Authorization: Bearer <Firebase_ID_Token>` to prove user identity)*
```json
{
  "client_id": "uuid-string",
  "code_challenge": "string",
  "code_challenge_method": "S256",
  "redirect_uri": "string (optional)",
  "state": "string (optional, echoed back on the redirect)"
}
```

**Response Schema (200 OK):**
```json
{
  "authorization_code": "short-lived-random-string",
  "redirect_uri": "http://localhost:54321/callback?code=...&state=..."
}
```

---

### 4.3 Token Exchange
**Endpoint:** `POST /api/oauth/token`
**Purpose:** Called by Claude to trade the `authorization_code` for Firebase Access/Refresh tokens. Uses `application/x-www-form-urlencoded`.

**Server-side behavior:**
*   **`authorization_code` grant:** looks up `code` in `oauth_codes`, **deletes it immediately** (anti-replay), then validates expiry, `client_id`, `redirect_uri` (loopback-normalized) and the PKCE transform: `BASE64URL(SHA256(ASCII(code_verifier)))` must equal the stored `code_challenge` (constant-time compare). On success it mints a Firebase custom token (`firebase-admin`) and exchanges it for a real ID + refresh token via the Identity Toolkit REST API.
*   **`refresh_token` grant:** exchanges a refresh token for a fresh ID token via the Secure Token REST API.
*   Unknown/used codes, expired codes, mismatches or failed PKCE return `400 invalid_grant`; an unknown `grant_type` returns `400 unsupported_grant_type`.
*   Requires the `FIREBASE_WEB_API_KEY` env var (same value as the portal's `NEXT_PUBLIC_FIREBASE_API_KEY`).

**Request Parameters (`authorization_code`):**
*   `grant_type`: `"authorization_code"`
*   `client_id`: `"uuid-string"` (optional; validated against the stored code if sent)
*   `code`: `"short-lived-random-string"`
*   `code_verifier`: `"string"` (PKCE validator)
*   `redirect_uri`: `"string"` (optional; validated against the stored code if sent)

**Request Parameters (`refresh_token`):**
*   `grant_type`: `"refresh_token"`
*   `refresh_token`: `"firebase-long-lived-string"`

**Response Schema (200 OK):**
```json
{
  "access_token": "firebase-jwt-string",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "firebase-long-lived-string"
}
```
