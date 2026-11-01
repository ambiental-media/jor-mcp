<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# ADR 008: Self-Contained Consent Portal

## 1. Context
The OAuth 2.1 consent UI lived in a separate Next.js repository and was deployed to the same Google Cloud Storage bucket as that repository's landing page. Two consequences followed:

*   Replicating Jor-MCP required cloning and deploying a second repository, so this repository was not sufficient to provision a working server.
*   Both repositories wrote to the same bucket. Either one running `rsync --delete-unmatched-destination-objects` could delete the other's objects, and both Next.js builds competed for the `/_next` path.

The backend already owns discovery, dynamic client registration, consent approval and token exchange. The consent UI is the only frontend the MCP server needs.

## 2. Decision
Move the consent UI into this repository as `portal/`, built as a static Next.js export and served from its own GCS bucket behind Cloud CDN.

The **standalone profile** is the default and the only documented replication path: the portal bucket is the load balancer's default backend, assets stay under `/_next`, and no other site is involved.

An **overlay profile** exists for deployments that already serve another site on the same host. It keeps that site as the default backend, routes four consent prefixes to the portal bucket, and builds the portal with `PORTAL_ASSET_PREFIX=/authorize-static` so the two Next.js asset trees do not collide.

## 3. Deployment Profiles

| | Standalone | Overlay |
| :--- | :--- | :--- |
| Audience | every replication | deployments with an existing site |
| Default backend | portal bucket | existing site bucket |
| Path rules | `/mcp*`, `/api/oauth*`, `/.well-known*` to Cloud Run | plus the four consent prefixes to the portal bucket |
| `PORTAL_ASSET_PREFIX` | empty | `/authorize-static` |
| Public consent URL | `/<locale>/authorize/` | identical |

## 4. Alternatives Considered

### 4.1 Subdomain for the portal
Clean asset isolation without a prefix, but adds a DNS record, a certificate entry, a Firebase authorized domain, an API-key referrer and two Cloud Run environment variables. Rejected: more replication steps for no functional gain.

### 4.2 Second bucket, no asset prefix
Two Next.js builds would serve assets from the same `/_next` path on one host, and the load balancer can route a path to only one backend. Rejected: the consent page would load the other site's bundle.

### 4.3 Serve the static export from Cloud Run
Removes the bucket and CDN, but reverses ADR 007, adds Node to the backend image build and puts consent behind a cold start. Rejected.

### 4.4 Migrate the entire site
One build and one bucket with no prefix, but the marketing site is not needed to provision or operate the MCP server. Deferred; the landing page is out of scope.

### 4.5 Keep the external repository
Status quo. Rejected: this repository stays incomplete for replication and the shared bucket remains a correctness hazard.

## 5. Consequences
*   `jor-mcp` is self-sufficient for provisioning the MCP server: one bucket, one static export, one deployment workflow.
*   No Python code, API contract, Firestore schema or IAM change for the backend.
*   The portal has its own manual deployment workflow (`cd-portal.yml`); it is not tied to the backend image release.
*   `NEXT_PUBLIC_*` values are inlined at build time, so a portal build with wrong values still compiles. The deployment workflow reads them from repository variables.
*   The marketing site is not reproducible from this repository, and living documentation no longer implies that it is.
*   `service.yaml` now sets `OAUTH_SERVER_BASE_URL`, `OAUTH_PORTAL_BASE_URL` and `CORS_ALLOWED_ORIGINS` from `${DOMAIN}`. Previously a replicated deployment inherited the reference domain in its discovery metadata.

## 6. Independence
The standalone profile has no build, deploy, code or documentation dependency on any external repository. The overlay profile is described generically as "an existing site on the same host"; it does not name, link to, or instruct anyone to create another repository.

Historical documents under `docs/*/3-history-and-specs/` keep their original references. They record what was true at the time and are not rewritten.

## 7. Migration and Rollback
New deployments follow the standalone provisioning steps and never create a second site.

Existing deployments that serve another site apply the overlay appendix: create the portal bucket, add the path rules, set `PORTAL_ASSET_PREFIX` and deploy. Once the external consent copy has been removed, rollback no longer restores it: redeploy the last known-good portal build with the `cd-portal` workflow (pass its tag as `ref`), which re-syncs the bucket and invalidates `/authorize*`, `/pt/authorize*` and `/en/authorize*`. Removing the four path rules is not a rollback to the old page — those objects were deleted from the site bucket — it only takes the consent routes offline.
