<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Firebase and Firestore Integration

## Architectural Decision: Why Serverless State?
We rely on Firestore rather than an in-memory cache or a provisioned Redis instance to maintain statelessness in the Cloud Run containers. This allows horizontal scaling to zero, maximizing FinOps efficiency while preventing rate-limit circumvention during traffic spikes.

## Runtime IAM Roles for the Firebase Admin SDK
The server does more than verify ID tokens. `src/api/oauth.py` also mints custom tokens, looks users up, and revokes refresh tokens, and each of those calls has its own IAM requirement on the Cloud Run runtime service account:

| Operation | Call | Required role |
| :--- | :--- | :--- |
| Verify an ID token | `auth.verify_id_token` | None — public signing certificates are fetched over HTTPS. |
| Mint a custom token | `auth.create_custom_token` | `roles/iam.serviceAccountTokenCreator`, bound on the runtime account itself: on Cloud Run the Admin SDK signs through the IAM `signBlob` API. |
| Look up a user | `auth.get_user` | `roles/firebaseauth.admin` |
| Revoke refresh tokens | `auth.revoke_refresh_tokens` | `roles/firebaseauth.admin` |

See the [deployment guide, section 2](../../2-replication/deployment-guide.md) for the full runtime role list.
