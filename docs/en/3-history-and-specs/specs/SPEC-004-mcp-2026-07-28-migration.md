<img src="/assets/ambiental-logo.png" alt="Ambiental Media Logo" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Jor-MCP Logo" style="float:left; vertical-align:middle" height="50em">

---


# SPEC-004: MCP 2026-07-28 Migration Assessment

**Origin:** ClickUp — [Ticket 012: Spike de Investigação — Oportunidades MCP 2026-07-28](https://app.clickup.com/t/86ak1gr4m)
**Status:** Draft — Investigation

## 1. Objective

Assess the impact of the MCP specification `2026-07-28` on the current `jor-mcp` server and produce a prioritized list of migration opportunities.

- [ ] Stateless-core impact on the current server documented.
- [ ] Infrastructure-simplification opportunities mapped (list caching, header routing).
- [ ] Authorization changes versus the current OAuth 2.1 proxy documented.
- [ ] Breaking changes and the 12-month deprecation window enumerated.
- [ ] Prioritized opportunities (impact × effort) and recommended next steps produced.

## 2. Context

MCP `2026-07-28` is the protocol's largest revision: the bidirectional stateful core becomes a request/response stateless protocol. Highlights:

- **Stateless core** — every request is self-describing; `initialize`/`initialized` and `Mcp-Session-Id` are retired.
- **Header-based routing** — `Mcp-Method` / `Mcp-Name` are required on Streamable HTTP POSTs.
- **Cacheable lists** — `ttlMs` + `cacheScope` on list/read results.
- **Authorization hardening** — RFC 9207 `iss`, CIMD replacing DCR.
- **Extensions framework** — Tasks, MCP Apps, Enterprise Managed Authorization (EMA).
- **12-month deprecation policy** formalized.

## 3. Current Architecture Snapshot

| Layer | Current state | `2026-07-28` exposure |
|---|---|---|
| Framework | `fastmcp 3.4.4`, `mcp 1.29.1` (`uv.lock`) | FastMCP `4.0.0b1` is the first to support the new spec |
| Transport | FastMCP `http_app()`, mounted at `/`; client connects to `/mcp/sse` | `/mcp/sse` = legacy HTTP+SSE **transport (deprecated)** |
| App state | Externalized — Firestore (rate limits), Firebase `tier` custom claim | Already stateless at the application layer |
| Authorization | Custom OAuth 2.1 proxy → Firebase Auth; DCR + PKCE + refresh; RFC 8414/9728 discovery | **DCR deprecated → CIMD**; RFC 9207 `iss` absent |
| Rate limiting | Firestore fixed-window (per-user monthly + per-IP short window) | Unaffected |
| Deployment | Cloud Run (min 0 / max 5) + GCLB (path routing) + Cloud CDN (portal) | Transport sessions tie replicas together |

> **Note on "gateway":** this project has no body-inspecting gateway. In [ADR-004](../adrs/004-poc-outcomes.md) the "remote, stateless gateway" *is* the FastMCP server itself. GCLB performs path routing only. The header-based routing item (§5.2) is therefore a forward-looking enabler, not the removal of an existing component.

## 4. Findings

### 4.1 Stateless migration

The application layer is already stateless (state lives in Firestore and Firebase claims); only **transport sessions** remain, inherited from FastMCP 3.x / SDK v1.

- `2026-07-28` retires the `initialize`/`initialized` handshake and the `Mcp-Session-Id` header; each request carries its protocol version and client capabilities in `_meta`.
- A new `server/discover` RPC (servers **MUST** implement) advertises supported versions, capabilities, and identity.
- Migration path: FastMCP 4 + MCP Python SDK v2, with client `mode="auto"` negotiation so one deployment serves both handshake-era and modern clients.
- **Interim option available today:** FastMCP 3.4.4 supports `http_app(stateless_http=True)` (or the `FASTMCP_STATELESS_HTTP=true` environment variable), which removes the need for session affinity before the 4.0 upgrade.

### 4.2 Infrastructure simplification

- **List caching.** `ttlMs` and `cacheScope` are now required on `tools/list`, `prompts/list`, `resources/list`, `resources/read`, and `resources/templates/list`. FastMCP 4 exposes `FastMCP(cache_ttl=..., cache_scope=...)`. This reduces re-fetching and stabilizes upstream prompt caches.
- **Deterministic ordering.** Servers **SHOULD** return `tools/list` in a stable order to improve client-side and prompt caching.
- **Header routing.** `Mcp-Method`, `Mcp-Name` (and `Mcp-Param-*`) are required on POSTs, letting a load balancer, WAF, or gateway route, meter, and authorize **without parsing the JSON body**. FastMCP does not strip these headers.
- **No deep packet inspection to remove today** — GCLB routes by path; there is no body-inspecting component in the current stack.

### 4.3 Authorization

Current implementation: a custom OAuth 2.1 proxy fronting Firebase Auth (Google Identity Platform).

| `2026-07-28` change | Current `jor-mcp` | Gap |
|---|---|---|
| CIMD preferred; DCR deprecated | `/api/oauth/register` implements DCR | Adopt CIMD (keep DCR fallback) |
| RFC 9207 `iss` in authorization responses; clients validate | Not emitted by the consent redirect | Portal must append `iss` |
| SEP-837 `application_type` in DCR | Ignored by `ClientRegistrationRequest` | Add validation |
| SEP-2352 credentials bound to issuer | Client-side concern | None server-side |

Scope agreed for this spike: **CIMD + RFC 9207 only** (no enterprise IdP / EMA migration).

### 4.4 Breaking changes and deprecations

**Retired (breaking):**

- `initialize` / `notifications/initialized` handshake.
- `Mcp-Session-Id` header; protocol-level sessions.
- `ping`, `logging/setLevel`, `notifications/roots/list_changed`.
- HTTP GET endpoint and `resources/subscribe` / `resources/unsubscribe` → replaced by `subscriptions/listen`.
- SSE stream resumability (`Last-Event-ID`, event IDs).

**New requirements:**

- `server/discover` (servers MUST); version mismatches answer `UnsupportedProtocolVersionError`.
- `resultType` on every result (`"complete"` | `"input_required"`).
- `extensions` field in capabilities.
- `CacheableResult` (`ttlMs`, `cacheScope`).
- `Mcp-Method` / `Mcp-Name` headers on POSTs, plus custom headers surfaced from tool parameters via `x-mcp-header`.

**Changed:**

- Resource-not-found error code `-32002` → `-32602`.
- JSON-RPC server-error range partitioned; codes renumbered — `HeaderMismatch` `-32001` → `-32020`, `MissingRequiredClientCapability` `-32003` → `-32021`, `UnsupportedProtocolVersion` `-32004` → `-32022`; `HeaderMismatchError` added to the schema.
- `inputSchema` / `outputSchema` loosened to any JSON Schema 2020-12 keywords; `structuredContent` may be any JSON value; `$ref` resolution and composition-keyword resource bounds defined.
- Removed `notifications/elicitation/complete` and the URL-mode `elicitationId`; servers correlate retries via `requestState`.
- Tasks moved to the `io.modelcontextprotocol/tasks` extension (poll `tasks/get`, `tasks/update`).
- Multi Round-Trip Requests (MRTR) replace server-initiated `sampling`/`elicitation`/`roots` requests.

**Deprecated (new implementations should not adopt):**

- **Roots, Sampling, Logging** — earliest removal: first revision released on or after **2027-07-28**.
- **Dynamic Client Registration (DCR)** — earliest removal: first revision released on or after **2027-07-28**.
- **`includeContext` `"thisServer"` / `"allServers"`** — removal follows the Sampling feature.
- **HTTP+SSE transport** — deprecated since `2025-03-26`; removal eligible three months after SEP-2596 reaches Final.

**Our exposure:** the `/mcp/sse` transport and DCR. We do not use sampling, roots, or logging. See [Appendix A](#appendix-a--full-change-inventory) for the complete change inventory.

### 4.5 Extensions and other observations

Official extensions use the identifier format `{vendor}/{name}`, are advertised through the `extensions` capability field, and are **disabled by default** (explicit opt-in).

| Extension | Purpose | Relevance to us |
|---|---|---|
| OAuth Client Credentials | OAuth 2.0 client-credentials flow for machine-to-machine auth | Possible for automated newsroom clients |
| Enterprise-Managed Authorization (EMA) | Centralized enterprise access control | Enterprise customers (out of scope now) |
| MCP Apps | Interactive UI rendered inline in conversations | Consent/UX experiments (out of scope) |
| MCP Tasks | Async long-running work, polling, durable handles | Future long-running ingestion |
| Skills over MCP | Discover/read Agent Skills via MCP resources | Reusable editorial workflows |

- `2026-07-28` documents OpenTelemetry trace-context propagation in `_meta` (`traceparent`, `tracestate`, `baggage`) — we already run OTel auto-instrumentation.
- MCP tunnels are out of scope for this assessment.

## 5. Prioritized Opportunities

| # | Opportunity | Impact | Effort | Notes |
|---|---|---|---|---|
| 1 | Enable `stateless_http=True` (works on 3.4.4 today) | High | XS | Removes session affinity pre-4.0 |
| 2 | Add `ttlMs` / `cacheScope` (`FastMCP(cache_ttl=, cache_scope=)`) | Medium | XS | Cacheable tool catalog |
| 3 | Deterministic `tools/list` ordering | Medium | S | Prompt-cache hit rate |
| 4 | Move client URL off `/mcp/sse` → Streamable HTTP | High | S | SSE transport deprecated |
| 5 | Upgrade FastMCP 3.4.4 → 4.0 + MCP SDK v2 | High | M | `mode="auto"` serves both eras |
| 6 | CIMD support in the proxy (DCR fallback retained) | Medium | M | Spec-standard registration |
| 7 | RFC 9207 `iss` (portal) + SEP-837 `application_type` | Low | S | Auth compliance |
| 8 | Header-based routing metadata for LB/gateway | Low now | S | Enables future metering without DPI |
| 9 | OTel `_meta` trace propagation | Low | S | Spec-documented |
| 10 | Tasks extension (long-running ingestion) | Future | L | Only if async work is needed |

## 6. Recommended Next Steps

1. Apply quick wins #1–#4 on `fastmcp 3.4.4` (no major upgrade required).
2. Prototype #5 in a branch; validate both protocol eras against Claude.
3. Implement #6–#7 as scoped follow-up tasks.
4. Track the deprecation window for `/mcp/sse` and DCR.
5. Re-evaluate #10 (Tasks) when asynchronous ingestion is required.

## 7. Out of Scope

- Enterprise IdP (Entra/Okta) migration and Enterprise Managed Authorization (EMA).
- MCP Apps extension.
- MCP tunnels.

## 8. Open Questions

- Target date to retire `/mcp/sse` and move clients to Streamable HTTP.
- Whether to adopt CIMD as the sole registration mechanism once DCR is removed.
- Whether Tasks will be needed for the ingestion roadmap.

## 9. Sources

- MCP `2026-07-28` specification — https://modelcontextprotocol.io/specification/2026-07-28
- MCP `2026-07-28` key changes / changelog — https://modelcontextprotocol.io/specification/2026-07-28/changelog
- MCP `2026-07-28` deprecated features registry — https://modelcontextprotocol.io/specification/2026-07-28/deprecated
- MCP extensions overview — https://modelcontextprotocol.io/docs/extensions/overview
- "The 2026-07-28 Specification" — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- "Bringing MCP 2026-07-28 to Claude" — https://claude.com/resources/articles/bringing-mcp-2026-07-28-to-claude
- FastMCP documentation — https://gofastmcp.com (stateless mode, CIMD, response caching, upgrade guide)

## Appendix A — Full Change Inventory

Complete crosswalk of the `2026-07-28` changelog against `jor-mcp`. `Affects us` is `Yes` (actionable now), `Later` (only if a feature is adopted), `Partial`, or `No`.

| # | Change | Affects us | Action |
|---|---|---|---|
| M1 | Protocol-level sessions / `Mcp-Session-Id` removed | Yes | Stateless mode (#1) |
| M2 | Stateless core; `initialize` handshake removed; `_meta` carries version/capabilities; `UnsupportedProtocolVersionError` on mismatch | Yes | FastMCP 4 (#5) |
| M3 | `server/discover` (MUST) | Yes | Provided by FastMCP 4 |
| M4 | `subscriptions/listen` replaces GET endpoint + `resources/subscribe`/`unsubscribe` | No | No subscriptions exposed |
| M5 | `ping`, `logging/setLevel`, `notifications/roots/list_changed` removed | No | Not used |
| M6 | Tasks moved to the `io.modelcontextprotocol/tasks` extension | Later | Re-evaluate (#10) |
| M7 | MRTR replaces server-initiated sampling/elicitation/roots | No | Not used |
| M8 | `resultType` required on all results | Yes | Handled by SDK v2 |
| M9 | SSE stream resumability removed | Yes | Part of `/mcp/sse` retirement (#4) |
| m1 | `extensions` capability field | Yes | Advertise only when adopting an extension |
| m2 | OTel `_meta` trace context | Later | Optional (#9) |
| m3 | Deterministic `tools/list` order (SHOULD) | Yes | #3 |
| m4 | `Mcp-Method` / `Mcp-Name` headers; `x-mcp-header` from tool params | Partial | #8; `x-mcp-header` only if needed |
| m5 | `ttlMs` / `cacheScope` (`CacheableResult`) | Yes | #2 |
| m6 | Resource-not-found `-32002` → `-32602` | Yes | Handled by SDK v2 |
| m7 | RFC 9207 `iss` in authorization responses | Yes | #7 |
| m8 | SEP-837 `application_type` in DCR | Yes | #7 |
| m9 | SEP-2352 credentials bound to issuer | No | Client-side |
| m10 | JSON Schema 2020-12 loosening; `structuredContent` any JSON; `$ref` bounds | Later | Review if output schemas change |
| m11 | `notifications/elicitation/complete` + `elicitationId` removed | No | Not used |
| m12 | Error-code allocation; renumbering; `HeaderMismatchError` | Later | Custom error handling |
| D1 | Roots, Sampling, Logging deprecated | No | Not used |
| D2 | HTTP+SSE transport deprecated | Yes | #4 |
| D3 | `includeContext` values deprecated | No | Not used |
| D4 | DCR deprecated → CIMD | Yes | #6 |
| S1 | `schema.json` min/max/default now `number` | No | Internal to the spec |
| G1 | Feature lifecycle / deprecation policy | Yes | Migration scheduling |
| P1 | SEP process workflow | No | Governance |
