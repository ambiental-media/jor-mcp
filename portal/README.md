# Jor-MCP Consent Portal

Static Next.js export of the OAuth 2.1 consent screen at `/authorize`.
The backend (`src/`, Cloud Run) owns discovery, client registration, consent
approval and token exchange. This app only renders the consent UI.

## Local development

```bash
npm ci
cp .env.example .env.local   # fill in the Firebase web app values
npm run dev                  # http://localhost:3000/pt/authorize/
```

Requires Node 24+ and GNU `realpath` (provided by coreutils; used by
`scripts/prepare-dist.sh`).

For local development point the backend at `http://localhost:8080`:

```bash
NEXT_PUBLIC_OAUTH_BACKEND_URL=http://localhost:8080
```

The backend already allows `http://localhost:3000` through
`CORS_ALLOWED_ORIGINS`.

## Environment variables

| Variable                           | Purpose                                                                                 |
| :--------------------------------- | :-------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_FIREBASE_API_KEY`     | same value as the backend's `FIREBASE_WEB_API_KEY`                                      |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Firebase Auth domain                                                                    |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID`  | Firebase project id                                                                     |
| `NEXT_PUBLIC_FIREBASE_APP_ID`      | Firebase web app id                                                                     |
| `NEXT_PUBLIC_OAUTH_BACKEND_URL`    | backend origin; empty means same origin                                                 |
| `PORTAL_ASSET_PREFIX`              | empty for the standalone profile; `/authorize-static` when another site shares the host |

`NEXT_PUBLIC_*` values are inlined at build time, so a production build must run
with the production values set.

## Scripts

| Command                                     | Description                     |
| :------------------------------------------ | :------------------------------ |
| `npm run dev`                               | development server              |
| `npm run build`                             | static export into `out/`       |
| `npm run lint`                              | ESLint                          |
| `npm run format:check`                      | Prettier check                  |
| `npm run test`                              | Vitest                          |
| `npm run test:coverage`                     | Vitest with coverage thresholds |
| `npm audit --audit-level=high`              | dependency audit                |
| `npm run prepare:dist -- out dist [prefix]` | build the sync tree             |

From the repository root, `make check-portal` runs install, lint, audit, tests,
both build profiles, and the dist preparation.

The coverage gate applies to `src/lib/oauth.js` and `src/lib/firebase.js`, which
hold the only branching logic. Page states are covered behaviorally by
`page.test.jsx`.

## Dependency overrides

`package.json` overrides `postcss` to `^8.5.32` and `@grpc/grpc-js` to `^1.14.7`.
Both are transitive dependencies of `next` and `firebase` respectively, pinned by
the upstream package to versions with known advisories. The build and the test
suite pass with the overrides.

Remove the `postcss` override when `next` is upgraded to `>= 16.4.3`, which fixes
the advisory upstream. Remove the `@grpc/grpc-js` override when `firebase` pulls a
patched version.

## Dependency audit policy

`npm audit --audit-level=high` runs in CI and in `make check-portal`. When an
upstream advisory has no fix, do not silence the gate: open an issue with the
advisory link, record the reachable/unreachable assessment, and add a review date.
Moderate findings are reported but not blocking.

## Deployment profiles

- **Standalone (default):** this bucket is the load balancer's default backend.
  Assets stay under `/_next/`. No asset prefix.
- **Overlay:** an existing site keeps the default backend and four path rules
  send the consent routes here. Set `PORTAL_ASSET_PREFIX=/authorize-static` so
  this build does not collide with the other site's `/_next` tree.

The bucket must be configured with `--web-main-page-suffix=index.html`; without
it, requests to `/pt/authorize/` return 404 because Next static export relies on
directory indexes. After every deploy, and after any change to the consent path
rules, invalidate `/authorize*`, `/pt/authorize*` and `/en/authorize*` — Cloud
CDN keeps HTML for up to an hour.

See `docs/en/2-replication/gcp-provisioning.md` for the infrastructure steps.
