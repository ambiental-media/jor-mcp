<img src="/assets/ambiental-logo.png" alt="Ambiental Media Logo" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Jor-MCP Logo" style="float:left; vertical-align:middle" height="50em">

---


# SPEC-003: Roles and Rate Limiting Adequacy

**Origin:** [Report: Roles and Role-Based Rate Limiting](../reports/roles-and-rate-limiting.md)
**Status:** Implemented

## 1. Objective

Make the role assigned manually by the administrator in the console actually govern the user's access and quota, and block any call from a user without an assigned role.

- [x] A user with `tier: "pro"` in Firestore receives the 2000 requests/month quota.
- [x] A user with no `tier` (or an unrecognised value) gets **HTTP 403** on `/mcp` and consumes no quota.
- [x] A user with no `tier` cannot complete consent at `/api/oauth/approve`.
- [x] Documentation and API contracts reflect the implemented behaviour.

## 2. Design Decisions

**Source of truth for the role:** the `allowed_users/{email}` Firestore document, curated manually by the Ambiental Media team through the console. This is what the [deployment guide](../../2-replication/deployment-guide.md) already instructs, and what the desired behaviour describes.

**Propagation to the JWT:** sync the Firestore `tier` field into a Firebase Auth custom claim via `auth.set_custom_user_claims(uid, {"tier": ...})` during `/api/oauth/approve`. Unlike `create_custom_token(uid, developer_claims=...)`, the claim persists on the user record and is re-issued on every token refresh, keeping the per-request cost at zero — `AuthMiddleware` keeps reading the role from the already-validated JWT, with no extra Firestore read.

**Blocking point:** `AuthMiddleware`. It already decodes the token and is the only place where rejection can happen before any quota is consumed. `tier` loses its `"basic"` default and becomes required, validated against the set of known roles; a missing or invalid value yields `403 Forbidden` (not `401`: the user is authenticated but not authorized).

**Failure policy:** the role check is fail-closed — unlike the rate limiters, which stay fail-open because they protect cost, not access. Since the role travels in the already-validated JWT, a Firestore outage does not affect requests from users holding a valid token.

## 3. Scope of Changes

### `src/api/oauth.py`
- `_is_email_allowed()` also returns the role from the document (or `None`) instead of a bare boolean.
- `oauth_approve()` rejects with `access_denied` when the user has no valid role, and calls `set_custom_user_claims(uid, {"tier": <role>})` before issuing the authorization code.

### `src/middleware/auth.py`
- `DecodedToken.tier` loses the `"basic"` default and becomes required, validated against the known roles.
- Token without `tier` or with an unknown role → `403` with the standard JSON body and a `warning` log carrying the `uid`.

### `src/config.py` and `src/middleware/rate_limit.py`
- The quota map moves out of the middleware and becomes `TIER_QUOTAS` in `config.py`: the single definition of which roles exist, consumed by `AuthMiddleware`, the rate limiter and the OAuth router without making `api/` depend on `middleware/`.
- The `user.get("tier", "basic")` fallback is removed: at that point the role is guaranteed.

### `jor-mcp-site`
- The `/authorize` screen treats a user without a role as access denied, reusing the message already shown for an inactive `status` (the decisive check stays in the backend; the portal's is UX only).

### Documentation
- `deployment-guide.md`: `tier` stops being "optional" and becomes a required field, with the explicit consequence that its absence blocks access.
- ADR-001 and ADR-006: record how the claims come to be populated and drop the reference to the non-existent `/admin` panel (or reclassify it as future work).

## 4. Testing Strategy

- `tests/test_auth_middleware.py`: token without `tier` → 403; token with an unknown role → 403; token with `basic`/`pro` → scope populated correctly.
- `tests/test_rate_limit_middleware.py`: the `pro` quota is actually enforced (`test_unknown_tier_falls_back_to_basic_limit` no longer makes sense and is replaced by the `AuthMiddleware` rejection scenario).
- `tests/test_oauth_router.py`: approve without a role → 403; approve with an unknown role → 403; approve with a role → `set_custom_user_claims` called with the correct value.
- `firebase_admin` stays mocked; no test touches the network.

## 5. Boundaries

- **Always:** keep Firestore as the source of truth for roles; keep the role check fail-closed; keep the rate limiters fail-open.
- **Ask first:** before introducing roles beyond `basic` and `pro`; before changing the `allowed_users` collection schema.
- **Never:** never infer a role from the email domain or any other heuristic; never log tokens or full claim sets.

## 6. Open Questions

- **Existing active users:** anyone already connected holds a credential issued before this change, which carries no `tier`. They must **re-consent** for the claim to be written — or the team runs a one-off script over `allowed_users` calling `set_custom_user_claims`. Decide which path before deploy.
