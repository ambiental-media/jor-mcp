<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# ADR 009: OAuth Redirect Host Allowlist

## 1. Context
Native MCP clients use RFC 7591 Dynamic Client Registration, which is intentionally open so Claude Desktop can connect without manual provisioning. Open registration also lets anyone register a client whose `redirect_uris` points at a host they control.

The consent flow then becomes a token-theft path: an attacker registers `https://attacker.example/cb` together with a PKCE challenge they generated, sends the victim that consent URL, and receives the authorization code once the victim clicks Allow. PKCE does not prevent this, because the attacker owns the verifier. The consent screen only shows `client_name`, which the attacker also controls.

The production `oauth_clients` collection shows that registration is not loopback-only: 185 clients redirect to `localhost` (75), `claude.ai` (100), `chatgpt.com` (7) and `www.braintrust.dev` (3). A loopback-only rule would break every remote connector.

## 2. Decision
Registration stays open, but redirect hosts are restricted:

*   Loopback hosts (`localhost`, `127.0.0.1`, `::1`) are always allowed, after the existing normalization, and may use plain `http` because the request never leaves the device (RFC 8252).
*   Every other host must appear in `OAUTH_ALLOWED_REDIRECT_HOSTS` (comma-separated environment variable) and must use `https`.
*   The rule is enforced twice: at `POST /api/oauth/register` (`400 invalid_redirect_uri`) and when resolving the redirect at `POST /api/oauth/approve` (`400 invalid_request`). The second check covers clients registered before the allowlist existed.
*   The reference deployment seeds `claude.ai,chatgpt.com,www.braintrust.dev`. A fork configures the clients it actually supports; with the variable empty, only loopback clients can complete consent.

## 3. Alternatives Considered

### 3.1 Loopback-only registration
Simplest and strongest, but breaks the 110 remote clients observed in production. Rejected.

### 3.2 Protected registration (initial access token or software statement)
RFC 7591's protected mode, but it removes the zero-configuration experience that ADR 006 exists to provide. Rejected for desktop clients; could be layered later for enterprise provisioning.

### 3.3 Display the redirect host on the consent screen only
Informative, but does not stop a user who clicks through. Rejected as the sole control.

### 3.4 Path-prefix allowlist
Entries like `claude.ai/api/mcp/auth_callback` are stricter than a host allowlist, but break whenever a provider changes its callback path. Kept as a future tightening step if one of the allowlisted domains ever exposes an open redirect.

## 4. Consequences
*   An attacker can no longer register a callback on a host the operator does not control, and pre-existing malicious client documents are refused at consent time.
*   Remote clients registered over plain `http` are refused as well. Production data contains only `https` remote registrations, so no live client breaks.
*   Supporting a new remote connector is an explicit configuration change and redeploy, not an automatic capability.
*   A missing host surfaces as a clear 400 with `invalid_redirect_uri` / `invalid_request`, not a silent failure.
*   Redirect hosts are logged (host only, never the complete URI or a token) when rejected.
*   No Firestore schema change; existing client documents stay as they are.
*   Registration sprawl is unchanged: the per-IP limiter bounds the rate, but duplicate clients accumulate. Pruning stale `oauth_clients` documents remains a separate follow-up.

## 5. Migration
1. Deploy the backend with `OAUTH_ALLOWED_REDIRECT_HOSTS` covering every host currently used by supported clients.
2. Verify one localhost consent and one remote consent end to end.
3. Rollback is the previous image; removing the variable alone reverts to loopback-only, which breaks remote connectors.
