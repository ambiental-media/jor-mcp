<img src="/assets/ambiental-logo.png" alt="Ambiental Media Logo" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Jor-MCP Logo" style="float:left; vertical-align:middle" height="50em">

---


# Report: Roles and Role-Based Rate Limiting

**Date:** 2026-08-10
**Type:** Investigation (spike)
**Scope:** `jor-mcp` (Python backend) and `jor-mcp-site` (Next.js portal)
**Status:** F1, F2, F3 and F5 resolved by [SPEC-003](../specs/SPEC-003-roles-adequacy.md). F4 stays as future work.

---

## 1. Executive Summary

Role-based rate limiting **is implemented in code but never exercised in production**: the role (named `tier` in the code) is read from a Firebase JWT custom claim that **no part of the system ever writes**. As a result every authenticated user falls back to the default `"basic"` value and receives the 500 requests/month quota, regardless of what is recorded in Firestore.

There are two material divergences from the desired behaviour:

1. No role assignment exists — neither manual nor automatic. The `tier` field documented on the `allowed_users` collection **is ignored by the code**.
2. There is no block for users without a role. A missing role silently falls back to `basic`, i.e. the system is fail-open exactly where it should be fail-closed.

The remediation is specified in **[SPEC-003: Roles and Rate Limiting Adequacy](../specs/SPEC-003-roles-adequacy.md)**.

---

## 2. How Roles Are Modelled Today

The term "role" does not appear in the code. The equivalent concept is **`tier`**, with two expected values:

| Role (`tier`) | Monthly quota | Environment variable |
| :--- | :--- | :--- |
| `basic` | 500 requests | `RATE_LIMIT_BASIC_REQUESTS` |
| `pro` | 2000 requests | `RATE_LIMIT_PRO_REQUESTS` |

Quotas are defined in [config.py:21-24](../../../../src/config.py#L21-L24) and mapped in [rate_limit.py:35-38](../../../../src/middleware/rate_limit.py#L35-L38).

`tier` is declared as a field of the decoded JWT in [auth.py:25-30](../../../../src/middleware/auth.py#L25-L30):

```python
class DecodedToken(BaseModel):
    uid: str
    email: str | None = None
    tier: str = "basic"
```

The `"basic"` default is the crux of every finding below: since the claim is never issued, **this default is the only value the system has ever produced**.

---

## 3. The Actual Flow, from Sign-Up to Request

| # | Step | Where | What happens to the role |
| :--- | :--- | :--- | :--- |
| 1 | Admin registers the user | Firebase Console → `allowed_users/{email}` | Writes `status: "active"` and, optionally, `tier` |
| 2 | User signs in with Google on the portal | [page.jsx:131-136](../../../../../jor-mcp-site/src/app/[locale]/authorize/page.jsx#L131-L136) | Reads `status` only; `tier` is not read |
| 3 | Portal calls `/api/oauth/approve` | [oauth.py:342-346](../../../../src/api/oauth.py#L342-L346) | `_is_email_allowed()` only checks `status == "active"`; `tier` is not read |
| 4 | Backend mints the tokens | [oauth.py:402](../../../../src/api/oauth.py#L402) | `auth.create_custom_token(uid)` — **no `developer_claims`** |
| 5 | MCP client calls `/mcp` | [auth.py:74-83](../../../../src/middleware/auth.py#L74-L83) | Token carries no `tier` → Pydantic applies the `"basic"` default |
| 6 | Rate limiter applies the quota | [rate_limit.py:76-77](../../../../src/middleware/rate_limit.py#L76-L77) | `_TIER_QUOTAS["basic"]` → 500 req/month for everyone |

Confirmed by scanning both repositories: **there is no call to `set_custom_user_claims` / `setCustomUserClaims` anywhere**, nor any read of the Firestore `tier` field.

---

## 4. How the Rate Limiter Reads the Role

`RateLimitMiddleware` ([rate_limit.py](../../../../src/middleware/rate_limit.py)) runs right after `AuthMiddleware` and relies exclusively on what the latter injected into the ASGI scope:

```python
uid: str = user["uid"]
tier: str = user.get("tier", "basic")
max_requests: int = _TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)
```

- **Algorithm:** monthly fixed window in Firestore, document `rate_limits/{uid}_YYYY-MM`, incremented atomically with `firestore.Increment(1)`.
- **Role source:** `scope["user"]["tier"]`, populated only by `AuthMiddleware` from the JWT. **No Firestore lookup is performed to resolve the role.**
- **Unknown role:** `_TIER_QUOTAS.get(tier, RATE_LIMIT_BASIC)` silently downgrades to the `basic` quota — behaviour locked in by `test_unknown_tier_falls_back_to_basic_limit` ([test_rate_limit_middleware.py:243](../../../../tests/test_rate_limit_middleware.py#L243)).
- **Missing scope:** if `scope["user"]` is absent the middleware forwards the request without metering it ([rate_limit.py:69-73](../../../../src/middleware/rate_limit.py#L69-L73)). That is safe today because `AuthMiddleware` has already rejected the request, but it places the entire blocking responsibility on it.
- **Firestore failure:** fail-open — the request passes and a `warning` is logged.

---

## 5. Findings

### F1 — The `tier` claim is never issued (root cause)
`_mint_firebase_tokens()` calls `auth.create_custom_token(uid)` with no `developer_claims`, and no code calls `set_custom_user_claims`. The resulting ID token has no `tier`. **Every user is `basic`.** The `pro` tier is effectively dead code.

### F2 — The Firestore `tier` field is decorative
The [deployment guide](../../2-replication/deployment-guide.md) instructs administrators to fill `tier` on `allowed_users/{email}`, stating it "determines the user's monthly rate limit quota". No line of code reads that field. A user marked `pro` in the console stays capped at 500 requests/month, with no error signal.

### F3 — Users without a role are not blocked
No validation rejects a request for missing a role. The missing-role path is a default (`"basic"`) plus a fallback (`_TIER_QUOTAS.get(...)`), both fail-open. This is the opposite of the desired behaviour.

### F4 — The `/admin` panel described in ADR-006 does not exist
[ADR-006](../adrs/006-oauth2-1-implementation-strategy.md) describes a B2B panel for promoting users from `basic` to `pro`. There is no `/admin` route in `jor-mcp-site` — the only administrative surface is the Firebase Console, which today writes to an ignored field (F2).

### F5 — Docs and ADRs describe a state that does not exist
[ADR-001](../adrs/001-auth-and-security.md) states that "the Firestore rate limiter reads `tier` claims from Firebase-issued JWTs to enforce differentiated traffic quotas". The read exists; the claim issuance does not. Docs, ADRs and code must be reconciled alongside the fix.

---

## 6. Gaps: Current × Desired

| Desired behaviour | Current state | Gap |
| :--- | :--- | :--- |
| Role assigned manually in the console at sign-up | Admin fills `tier` on `allowed_users`, but the field is ignored | **Critical** — assignment has no effect (F1, F2) |
| Users without a role cannot call the system | Missing role → `basic` default → 500 req/month granted | **Critical** — fail-open where it should be fail-closed (F3) |
| Role-differentiated rate limiting | Implemented, but fed by a claim that is never issued | **Critical** — `pro` unreachable (F1) |
| Administrative surface for managing roles | Firebase Console only | **Medium** — acceptable short term (F4) |

---

## 7. Next Step

All divergences above are consolidated into the remediation task **[SPEC-003: Roles and Rate Limiting Adequacy](../specs/SPEC-003-roles-adequacy.md)**, which defines the source of truth for roles, the fail-closed blocking point and the documentation reconciliation.
