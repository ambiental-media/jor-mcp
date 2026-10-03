<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Firebase and Firestore Integration

`jor-mcp` uses Google Cloud for three things: **authenticating users** (Firebase Auth), **storing OAuth state** (Firestore) and **counting requests for rate limits** (Firestore). Content sources (WordPress and GitHub) do not go through Google.

Because of this, the server needs a Google Cloud project with Firebase Auth and Firestore enabled **even when running locally**.

## 1. Startup (`src/server.py`)

When the server starts, the lifespan handler:

*   calls `firebase_admin.initialize_app()` with no arguments, so it uses Application Default Credentials (the service account on Cloud Run; `gcloud auth application-default login` on a developer machine);
*   creates a single `FirestoreAsyncClient(database=FIRESTORE_DATABASE_ID)`, shared by the rest of the code through `get_firestore_client()`.

## 2. Firebase Auth: who can call the tools (`src/middleware/auth.py`)

`AuthMiddleware` intercepts **every** request to the MCP endpoint:

*   reads the `Authorization: Bearer <token>` header;
*   validates the token with `auth.verify_id_token(...)`, allowing 60 seconds of clock skew;
*   extracts the `uid` and a `tier` claim (`basic` or `pro`; defaults to `basic` when absent) and passes both to the rate limiter;
*   when the token is missing or invalid, answers **401** with `WWW-Authenticate: Bearer resource_metadata=...`. This header is what makes Claude Desktop open the browser to log in.

Only `/health`, `/.well-known/*` and `/api/oauth/*` skip this check.

## 3. OAuth 2.1 proxy (`src/api/oauth.py`)

MCP clients such as Claude Desktop speak OAuth, not Firebase. The server bridges the two:

| Step | Endpoint | Google usage |
|---|---|---|
| Discovery | `GET /.well-known/oauth-*` | none (metadata only) |
| Client registration (DCR) | `POST /api/oauth/register` | writes to the **`oauth_clients`** collection |
| Consent | separate Next.js portal (`jor-mcp-site`) | Google SSO login through Firebase in the browser |
| Approval | `POST /api/oauth/approve` | verifies the portal's Firebase token, checks **`allowed_users`**, stores the code and PKCE challenge in **`oauth_codes`** (valid for 10 minutes) |
| Code exchange | `POST /api/oauth/token` | reads and **deletes** the code (no replay), verifies PKCE S256, creates a custom token with `auth.create_custom_token(uid)` and exchanges it for ID and refresh tokens through the **Identity Toolkit API** (`accounts:signInWithCustomToken`) |
| Refresh | `POST /api/oauth/token` (`refresh_token`) | **Secure Token API** (`securetoken.googleapis.com`) |

The allow-list is the `allowed_users` collection: each document ID is a lowercase email, and access is granted only when `status == "active"`. It is curated manually (e.g. in the Firebase console).

## 4. Firestore: rate limits

Both counters use a fixed window and an atomic `firestore.Increment(1)`, so multiple Cloud Run instances share the same count.

*   **Per user** (`src/middleware/rate_limit.py`): collection `rate_limits`, one document per `{uid}_{YYYY-MM}`. Monthly quota of 500 requests for `basic` and 2000 for `pro` (`RATE_LIMIT_BASIC_REQUESTS`, `RATE_LIMIT_PRO_REQUESTS`). Over the quota the server answers **429** with `Retry-After` until the start of the next month.
*   **Per IP** (`src/middleware/ip_rate_limit.py`): collection `ip_rate_limits`. Applies only to the unauthenticated routes (`/api/oauth/*` and `/.well-known/*`) and prevents anyone from flooding Firestore with DCR registrations. Default is 60 requests per minute. Documents carry an `expires_at` field meant for a Firestore TTL policy.

Both limiters **fail open**: if Firestore returns an error, the request goes through. A database outage does not take the service down, but limits are not enforced while it lasts.

## 5. Collections summary

| Collection | Contents |
|---|---|
| `allowed_users` | email allow-list |
| `oauth_clients` | registered MCP clients |
| `oauth_codes` | short-lived authorization codes with PKCE |
| `rate_limits` | monthly per-user counters |
| `ip_rate_limits` | per-IP, per-minute counters |

Collection names can be overridden through environment variables; see [Configuration and Environment](../../2-replication/configuration-and-env.md).

## 6. Operations notes

*   **Native mode is required.** The code uses the native Firestore client (`google.cloud.firestore_v1`), which does not work with a database in Datastore mode.
*   **Granting a user access:** create a document in `allowed_users` whose ID is the user's email in lowercase, with the field `status: "active"`.
*   **Granting the `pro` tier:** the tier comes from a Firebase custom claim. Set it with the Admin SDK, e.g. `auth.set_custom_user_claims(uid, {"tier": "pro"})`. This repository does not automate it.

## Architectural Decision: Why Serverless State?
We rely on Firestore rather than an in-memory cache or a provisioned Redis instance to maintain statelessness in the Cloud Run containers. This allows horizontal scaling to zero, maximizing FinOps efficiency while preventing rate-limit circumvention during traffic spikes.