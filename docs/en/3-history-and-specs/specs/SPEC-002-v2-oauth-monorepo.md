<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# SPEC-002: OAuth 2.1 Implementation Strategy

## 1. Objective
Transition `jor-mcp` from a basic Resource Server to an OAuth 2.1 Defensive Proxy, decoupling the user consent UI to the `jor-mcp-site` static export.

### Success Criteria
- [ ] Claude Desktop completes the 4-phase PKCE flow natively without user configuration files.
- [ ] Python proxy correctly normalizes `localhost` / `127.0.0.1` DCR mismatches.
- [ ] Python proxy correctly mints short-lived Access Tokens and long-lived Refresh Tokens via the Firebase Admin SDK.
- [ ] The static Next.js frontend successfully triggers the `/api/oauth/approve` backend endpoint via CORS after validating the user against a Firestore whitelist.

## 2. Tech Stack & Infrastructure
- **Backend:** Python 3.12, `fastmcp`, `uvicorn`, `firebase-admin`, `google-cloud-firestore`.
- **Frontend:** Next.js (Static Export) hosted on **Google Cloud Storage (GCS) Bucket** behind Cloud CDN, React, Firebase Auth JS SDK (Google SSO only).
- **Routing:** GCP Global Load Balancer (`/mcp/*` and `/api/oauth/*` -> Backend Serverless NEG; `/*` -> GCS Backend Bucket).
- **Identity:** Strict B2B Whitelist. Public sign-ups disabled. Administrators provision users manually via the Firebase Console.

## 3. Commands (Python Backend)
- **Dev:** `uv run uvicorn src.server:app --reload`
- **Test:** `make check`
- **Lint:** `uv run ruff check . --fix`
- **Format:** `uv run ruff format .`
- **Typecheck:** `uv run mypy .`

## 4. Project Structure
- `src/api/` -> New directory for OAuth HTTP endpoints (outside FastMCP context).
- `src/middleware/` -> Rate limiting and Auth parsing.
- `src/services/` -> WordPress and GitHub integrations.

## 5. Code Style & Conventions
- **Absolute imports:** Always anchor at `src`.
- **Typing:** Use Python 3.12+ native syntax (e.g., `str | None`).
- **Boundaries:** All OAuth payloads must be validated using Pydantic models in `src/api/`.

## 6. Testing Strategy
- Use `pytest-asyncio`.
- Mock `firebase_admin` to avoid network calls.
- Use `TestClient` for HTTP endpoint verification.

## 7. Boundaries
- **Always do:** Validate all incoming OAuth payloads using Pydantic. Normalize redirect URIs to `localhost`. Enforce the Firestore whitelist check on both frontend (`/authorize`) and backend (`/api/oauth/approve`).
- **Ask first:** Before adding new external dependencies to `pyproject.toml`. Before altering Firestore collection schemas.
- **Never do:** Never return raw HTML from Python; UI remains in the Next.js portal. Never log raw Auth codes or Access Tokens.

## Open Questions
- None.
