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
    and `https://jor-mcp.ambiental.media` (prod portal).
*   **Allowed Methods:** `GET`, `POST`, `OPTIONS`.
*   **Allowed Headers:** `Authorization`, `Content-Type`.

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

### 4.1 Dynamic Client Registration (DCR)
**Endpoint:** `POST /api/oauth/register`
**Purpose:** Called by Claude Desktop to register itself and obtain a `client_id`.

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

**Request Schema:**
*(Requires `Authorization: Bearer <Firebase_ID_Token>` to prove user identity)*
```json
{
  "client_id": "uuid-string",
  "code_challenge": "string",
  "redirect_uri": "string"
}
```

**Response Schema (200 OK):**
```json
{
  "authorization_code": "short-lived-random-string",
  "redirect_uri": "http://127.0.0.1:54321/callback?code=..."
}
```

---

### 4.3 Token Exchange
**Endpoint:** `POST /api/oauth/token`
**Purpose:** Called by Claude to trade the `authorization_code` for Firebase Access/Refresh tokens. Uses `application/x-www-form-urlencoded`.

**Request Parameters:**
*   `grant_type`: `"authorization_code"`
*   `client_id`: `"uuid-string"`
*   `code`: `"short-lived-random-string"`
*   `code_verifier`: `"string"` (PKCE validator)
*   `redirect_uri`: `"string"`

**Response Schema (200 OK):**
```json
{
  "access_token": "firebase-jwt-string",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "firebase-long-lived-string"
}
```
