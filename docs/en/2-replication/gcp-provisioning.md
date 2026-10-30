<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# GCP Provisioning Guide

Commands to provision the Jor-MCP GCP infrastructure, in execution order. Before you start, check the [Prerequisites](prerequisites.md).

## Step 0 – Variables

The following steps use these variables. Run all steps in the same terminal session.

```bash
# --- Fill in for your newsroom ---
export PROJECT_ID="my-newsroom-mcp"
export REGION="us-central1"
export FIRESTORE_LOCATION="nam5"
export DOMAIN="mcp.example.org"
export AR_REPO="jor-mcp"
export SERVICE="jor-mcp-server"
export GCS_BUCKET="jor-mcp-site-${PROJECT_ID}"
# SERVICE and AR_REPO are wired into the repository: SERVICE must equal
# service.yaml `metadata.name` and the GCP_IMAGE_NAME variable below, and
# AR_REPO must equal the GCP_AR_REPO variable.

# Point gcloud to the project
gcloud config set project "$PROJECT_ID"

# Derived values
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export RUNNER_SA="jor-mcp-runner@${PROJECT_ID}.iam.gserviceaccount.com"
export CI_SA="github-actions-ci@${PROJECT_ID}.iam.gserviceaccount.com"
```

Reference: [`gcloud config set`](https://cloud.google.com/sdk/gcloud/reference/config/set) · [`gcloud projects describe`](https://cloud.google.com/sdk/gcloud/reference/projects/describe)

## Step 0.1 – Repository configuration

The GitHub Actions workflows read the deployment targets from repository
variables, so a fork deploys to its own project without editing any file. An
unset variable falls back to the Ambiental Media deployment, so set all of them
before enabling the workflows. Configure in **Settings → Secrets and variables →
Actions**:

| Type | Name | Value |
| :--- | :--- | :--- |
| Variable | `GCP_PROJECT_ID` | `$PROJECT_ID` |
| Variable | `GCP_PROJECT_NUMBER` | `$PROJECT_NUMBER` |
| Variable | `GCP_REGION` | `$REGION` |
| Variable | `GCP_AR_REPO` | `$AR_REPO` |
| Variable | `GCP_IMAGE_NAME` | `$SERVICE` |
| Variable | `FIREBASE_PROJECT_ID` | `$PROJECT_ID` |
| Variable | `WORDPRESS_API_URL` | Base URL of your WordPress API |
| Variable | `MCP_GITHUB_REPOS` | `org/repo-a,org/repo-b` |
| Variable | `OTEL_EXPORTER_OTLP_ENDPOINT` | Leave empty unless you run an OTLP collector |
| Variable | `FIREBASE_WEB_API_KEY` | Value from step 6.1 |
| Secret | `GCP_SA_KEY` | base64 key created in step 3 |

## Step 1 – APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  firestore.googleapis.com \
  firebase.googleapis.com \
  firebaserules.googleapis.com \
  identitytoolkit.googleapis.com \
  securetoken.googleapis.com \
  apikeys.googleapis.com \
  iamcredentials.googleapis.com \
  cloudtrace.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

Reference: [`gcloud services enable`](https://cloud.google.com/sdk/gcloud/reference/services/enable)

## Step 2 – Artifact Registry

```bash
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Docker images for Jor-MCP"
```

Reference: [`gcloud artifacts repositories create`](https://cloud.google.com/sdk/gcloud/reference/artifacts/repositories/create)

## Step 3 – Service accounts and IAM

| Service account | Purpose | Roles |
| :--- | :--- | :--- |
| `jor-mcp-runner` | Cloud Run runtime identity | Project: `datastore.user`, `secretmanager.secretAccessor`, `cloudtrace.agent`, `logging.logWriter`, `monitoring.metricWriter`, `firebaseauth.admin`. On itself: `iam.serviceAccountTokenCreator` |
| `github-actions-ci` | Image publishing and deploys from GitHub Actions | Project: `artifactregistry.writer`, `run.admin`. On `MCP_GITHUB_TOKEN` and `JWT_SECRET`: `secretmanager.secretAccessor` (only if a deploy rejects the secret). On `jor-mcp-runner`: `iam.serviceAccountUser` |

The reason for each runtime role is described in section 2 of the [Deployment Guide](deployment-guide.md). `roles/run.sourceDeveloper` is not required: it only covers `gcloud run deploy --source`, which no workflow uses.

```bash
# Runtime SA for Cloud Run
gcloud iam service-accounts create jor-mcp-runner \
  --display-name="jor-mcp-runner" \
  --description="Dedicated runtime identity for the jor-mcp-server Cloud Run service"

for ROLE in roles/datastore.user roles/secretmanager.secretAccessor roles/cloudtrace.agent \
            roles/logging.logWriter roles/monitoring.metricWriter roles/firebaseauth.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${RUNNER_SA}" --role="$ROLE" --condition=None
done

# Firebase custom-token signing (signBlob), scoped to the runtime SA itself
gcloud iam service-accounts add-iam-policy-binding "$RUNNER_SA" \
  --member="serviceAccount:${RUNNER_SA}" --role="roles/iam.serviceAccountTokenCreator"

# CI/CD SA for GitHub Actions
gcloud iam service-accounts create github-actions-ci \
  --display-name="github-actions-ci" \
  --description="Used by GitHub Actions to push images and deploy to Cloud Run"

for ROLE in roles/artifactregistry.writer roles/run.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CI_SA}" --role="$ROLE" --condition=None
done

# Allow the CI SA to deploy services that run as the runtime SA
gcloud iam service-accounts add-iam-policy-binding "$RUNNER_SA" \
  --member="serviceAccount:${CI_SA}" --role="roles/iam.serviceAccountUser"

# JSON key for GitHub Actions, written OUTSIDE the repository
KEY_DIR="$(mktemp -d)"
gcloud iam service-accounts keys create "${KEY_DIR}/github-actions-ci-key.json" --iam-account="$CI_SA"
base64 -w0 "${KEY_DIR}/github-actions-ci-key.json" > "${KEY_DIR}/github-actions-ci-key.b64"
echo "Paste ${KEY_DIR}/github-actions-ci-key.b64 into the GCP_SA_KEY secret, then delete: ${KEY_DIR}"
```

On macOS, use `base64 -i "${KEY_DIR}/github-actions-ci-key.json" > "${KEY_DIR}/github-actions-ci-key.b64"`. The `.b64` file content is the `GCP_SA_KEY` repository secret described in section 8 of the [Deployment Guide](deployment-guide.md).

> **Prefer keyless authentication.** This guide uses a long-lived service account key because the current workflows expect `GCP_SA_KEY`. [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation) (`google-github-actions/auth` with `workload_identity_provider`) removes the key and its rotation burden entirely. If you keep the key, rotate it at least every 90 days and never write it inside the repository.

Reference: [`gcloud iam service-accounts create`](https://cloud.google.com/sdk/gcloud/reference/iam/service-accounts/create) · [`gcloud projects add-iam-policy-binding`](https://cloud.google.com/sdk/gcloud/reference/projects/add-iam-policy-binding) · [`gcloud iam service-accounts add-iam-policy-binding`](https://cloud.google.com/sdk/gcloud/reference/iam/service-accounts/add-iam-policy-binding) · [`gcloud iam service-accounts keys create`](https://cloud.google.com/sdk/gcloud/reference/iam/service-accounts/keys/create)

## Step 4 – Secret Manager

```bash
# GitHub PAT with read access to the editorial repos
printf '%s' "ghp_xxx" | gcloud secrets create MCP_GITHUB_TOKEN \
  --replication-policy=automatic --data-file=-

# Random value
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create JWT_SECRET \
  --replication-policy=automatic --data-file=-

# Optional: grant the CI SA read access to these two secrets only.
# Cloud Run resolves mounted secrets with the runtime identity, so the deployer
# normally needs nothing here. Add it only if a deploy fails with
# "Permission denied on secret".
for SECRET in MCP_GITHUB_TOKEN JWT_SECRET; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${CI_SA}" --role="roles/secretmanager.secretAccessor"
done
```

Reference: [`gcloud secrets create`](https://cloud.google.com/sdk/gcloud/reference/secrets/create)

## Step 5 – Firestore

```bash
gcloud firestore databases create \
  --database="(default)" --location="$FIRESTORE_LOCATION" --type=firestore-native

# Point-in-time recovery
gcloud firestore databases update --database="(default)" --enable-pitr

# Reclaim expired per-IP rate-limit windows (see configuration-and-env.md §2.1)
gcloud firestore fields ttls update expires_at \
  --collection-group=ip_rate_limits --enable-ttl

# Daily backup, kept for 98 days
gcloud firestore backups schedules create \
  --database="(default)" --recurrence=daily --retention=98d
```

Reference: [`gcloud firestore databases create`](https://cloud.google.com/sdk/gcloud/reference/firestore/databases/create) · [`gcloud firestore databases update`](https://cloud.google.com/sdk/gcloud/reference/firestore/databases/update) · [`gcloud firestore fields ttls update`](https://cloud.google.com/sdk/gcloud/reference/firestore/fields/ttls/update) · [`gcloud firestore backups schedules create`](https://cloud.google.com/sdk/gcloud/reference/firestore/backups/schedules/create)

## Step 6 – Firebase Auth

**6.1 – Add Firebase to the project and create the web app**

```bash
firebase projects:addfirebase "$PROJECT_ID"
firebase apps:create WEB jor-mcp --project "$PROJECT_ID"

# Use the App ID printed above to get the web config, then copy its apiKey
firebase apps:sdkconfig WEB <APP_ID> --project "$PROJECT_ID"
export FIREBASE_WEB_API_KEY="AIza..."
```

**6.2 – In the Firebase Console, under Authentication**

1. Click *Get started*.
2. Under *Sign-in method*, enable the **Google** provider and keep **Email/Password** disabled.
3. Under *Settings → User actions*, uncheck *Enable create (sign-up)*.

**6.3 – Authorized domains**

```bash
curl -sS -X PATCH \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "x-goog-user-project: $PROJECT_ID" \
  -H "Content-Type: application/json" \
  "https://identitytoolkit.googleapis.com/admin/v2/projects/${PROJECT_ID}/config?updateMask=authorizedDomains" \
  -d "{\"authorizedDomains\":[\"localhost\",\"${PROJECT_ID}.firebaseapp.com\",\"${PROJECT_ID}.web.app\",\"${DOMAIN}\"]}"
```

Reference: [Firebase CLI – commands](https://firebase.google.com/docs/cli#command_reference) · [Google sign-in (Firebase Auth)](https://firebase.google.com/docs/auth/web/google-signin) · [Identity Toolkit `projects.updateConfig`](https://cloud.google.com/identity-platform/docs/reference/rest/v2/projects/updateConfig)

## Step 7 – Image and Cloud Run

Run from the root of your fork. `service.yaml` defines the service: ingress restricted to the load balancer, 0 to 5 instances, 1 vCPU, 1Gi, running as `jor-mcp-runner`.

```bash
# Build and push the image
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
export IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}:latest"
docker build -t "$IMAGE_URL" .
docker push "$IMAGE_URL"

# Values injected into service.yaml
export GCP_PROJECT_ID="$PROJECT_ID"
export GCP_PROJECT_NUMBER="$PROJECT_NUMBER"
export GCP_REGION="$REGION"
export FIREBASE_PROJECT_ID="$PROJECT_ID"
export WORDPRESS_API_URL="https://example.org/wp-json"
export MCP_GITHUB_REPOS="org/repo-a,org/repo-b"
# Leave empty unless you run an OTLP collector. A dead endpoint makes every
# batch retry and fail (see configuration-and-env.md §2.4). To export spans,
# also add OTEL_TRACES_EXPORTER=otlp to service.yaml.
export OTEL_EXPORTER_OTLP_ENDPOINT=""
# FIREBASE_WEB_API_KEY was exported in step 6.1

# Render and deploy the service
envsubst '${IMAGE_URL} ${GCP_PROJECT_NUMBER} ${GCP_PROJECT_ID} ${GCP_REGION} ${FIREBASE_PROJECT_ID} ${WORDPRESS_API_URL} ${MCP_GITHUB_REPOS} ${OTEL_EXPORTER_OTLP_ENDPOINT} ${FIREBASE_WEB_API_KEY}' \
  < service.yaml | gcloud run services replace - --region="$REGION"

# Allow unauthenticated invocations (access is restricted by ingress and enforced by the app)
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" --member=allUsers --role=roles/run.invoker
```

Reference: [`gcloud auth configure-docker`](https://cloud.google.com/sdk/gcloud/reference/auth/configure-docker) · [`docker build`](https://docs.docker.com/reference/cli/docker/buildx/build/) · [`docker push`](https://docs.docker.com/reference/cli/docker/image/push/) · [`gcloud run services replace`](https://cloud.google.com/sdk/gcloud/reference/run/services/replace) · [`gcloud run services add-iam-policy-binding`](https://cloud.google.com/sdk/gcloud/reference/run/services/add-iam-policy-binding)

## Step 8 – Load balancer (Cloud Armor optional)

```
HTTPS :443  ip-lb-jor-mcp → lb-jor-mcp-target-proxy (cert-ip-jor-mcp) → lb-jor-mcp
              ├── /mcp/*, /api/oauth/*, /.well-known/*  → back-end-jor-mcp → neg-cloudrun-jor-mcp → Cloud Run
              └── /* (default)                          → back-end-bucket-jor-mcp (Cloud CDN → GCS)
            back-end-jor-mcp carries Cloud Armor when it is enabled (step 8.2)
HTTP  :80   ip-lb-jor-mcp-forwarding-rule → ip-lb-jor-mcp-target-proxy → ip-lb-jor-mcp-redirect (301 → HTTPS)
```

Cloud Armor is optional: the server already rate-limits per user in Firestore,
and the policy adds a fixed monthly cost. Enable step 8.2 only if you expect
volumetric abuse.

**8.1 – IP, NEG and backend service**

```bash
gcloud compute addresses create static-ip-addr-jor-mcp --global --ip-version=IPV4
export LB_IP="$(gcloud compute addresses describe static-ip-addr-jor-mcp --global --format='value(address)')"

gcloud compute network-endpoint-groups create neg-cloudrun-jor-mcp \
  --region="$REGION" --network-endpoint-type=serverless --cloud-run-service="$SERVICE"

gcloud compute backend-services create back-end-jor-mcp \
  --global --load-balancing-scheme=EXTERNAL_MANAGED --protocol=HTTPS \
  --timeout=3600s --enable-logging --logging-sample-rate=0.1
gcloud compute backend-services add-backend back-end-jor-mcp --global \
  --network-endpoint-group=neg-cloudrun-jor-mcp --network-endpoint-group-region="$REGION"
```

**8.2 – Cloud Armor (500 requests per minute per IP)**

```bash
gcloud compute security-policies create jor-mcp-backend-policy --type=CLOUD_ARMOR
gcloud compute security-policies rules create 2147483646 \
  --security-policy=jor-mcp-backend-policy --src-ip-ranges="*" \
  --action=throttle --conform-action=allow --exceed-action=deny-403 \
  --rate-limit-threshold-count=500 --rate-limit-threshold-interval-sec=60 \
  --enforce-on-key=IP --description="Default rate limiting rule"
gcloud compute backend-services update back-end-jor-mcp --global \
  --security-policy=jor-mcp-backend-policy
```

**8.3 – Frontend bucket, URL map, certificate and HTTPS frontend**

The URL map splits traffic: `/mcp/*`, `/api/oauth/*` and `/.well-known/*` go to
Cloud Run, everything else is served by the static portal in the GCS bucket
(see [Load Balancer Configuration](load-balancer-config.md) §3).

```bash
# Static portal bucket, served through Cloud CDN
gcloud storage buckets create "gs://${GCS_BUCKET}" \
  --location="$REGION" --uniform-bucket-level-access
# Upload the portal build output to the bucket root before going further.
gcloud compute backend-buckets create back-end-bucket-jor-mcp \
  --gcs-bucket-name="$GCS_BUCKET" --enable-cdn

# The heredoc is unquoted on purpose: ${PROJECT_ID} and ${DOMAIN} must expand.
gcloud compute url-maps import lb-jor-mcp --global --quiet <<EOF
name: lb-jor-mcp
defaultService: projects/${PROJECT_ID}/global/backendBuckets/back-end-bucket-jor-mcp
hostRules:
- hosts:
  - ${DOMAIN}
  pathMatcher: jor-mcp-paths
pathMatchers:
- name: jor-mcp-paths
  defaultService: projects/${PROJECT_ID}/global/backendBuckets/back-end-bucket-jor-mcp
  pathRules:
  - paths:
    - /mcp
    - /mcp/*
    service: projects/${PROJECT_ID}/global/backendServices/back-end-jor-mcp
  - paths:
    - /api/oauth
    - /api/oauth/*
    service: projects/${PROJECT_ID}/global/backendServices/back-end-jor-mcp
  - paths:
    - /.well-known
    - /.well-known/*
    service: projects/${PROJECT_ID}/global/backendServices/back-end-jor-mcp
EOF

gcloud compute ssl-certificates create cert-ip-jor-mcp --global --domains="$DOMAIN"

gcloud compute target-https-proxies create lb-jor-mcp-target-proxy --global \
  --url-map=lb-jor-mcp --ssl-certificates=cert-ip-jor-mcp

gcloud compute forwarding-rules create ip-lb-jor-mcp --global \
  --load-balancing-scheme=EXTERNAL_MANAGED --network-tier=PREMIUM \
  --address=static-ip-addr-jor-mcp --target-https-proxy=lb-jor-mcp-target-proxy --ports=443
```

**8.4 – HTTP → HTTPS redirect**

```bash
gcloud compute url-maps import ip-lb-jor-mcp-redirect --global --quiet <<'EOF'
name: ip-lb-jor-mcp-redirect
defaultUrlRedirect:
  httpsRedirect: true
  redirectResponseCode: MOVED_PERMANENTLY_DEFAULT
EOF

gcloud compute target-http-proxies create ip-lb-jor-mcp-target-proxy --global \
  --url-map=ip-lb-jor-mcp-redirect

gcloud compute forwarding-rules create ip-lb-jor-mcp-forwarding-rule --global \
  --load-balancing-scheme=EXTERNAL_MANAGED --network-tier=PREMIUM \
  --address=static-ip-addr-jor-mcp --target-http-proxy=ip-lb-jor-mcp-target-proxy --ports=80
```

Reference: [`addresses create`](https://cloud.google.com/sdk/gcloud/reference/compute/addresses/create) · [`network-endpoint-groups create`](https://cloud.google.com/sdk/gcloud/reference/compute/network-endpoint-groups/create) · [`backend-services create`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-services/create) · [`backend-services add-backend`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-services/add-backend) · [`backend-services update`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-services/update) · [`security-policies create`](https://cloud.google.com/sdk/gcloud/reference/compute/security-policies/create) · [`security-policies rules create`](https://cloud.google.com/sdk/gcloud/reference/compute/security-policies/rules/create) · [`backend-buckets create`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-buckets/create) · [`storage buckets create`](https://cloud.google.com/sdk/gcloud/reference/storage/buckets/create) · [`url-maps import`](https://cloud.google.com/sdk/gcloud/reference/compute/url-maps/import) · [`ssl-certificates create`](https://cloud.google.com/sdk/gcloud/reference/compute/ssl-certificates/create) · [`target-https-proxies create`](https://cloud.google.com/sdk/gcloud/reference/compute/target-https-proxies/create) · [`target-http-proxies create`](https://cloud.google.com/sdk/gcloud/reference/compute/target-http-proxies/create) · [`forwarding-rules create`](https://cloud.google.com/sdk/gcloud/reference/compute/forwarding-rules/create)

## Step 9 – DNS and certificate

In your DNS provider, create an `A` record pointing `$DOMAIN` to `$LB_IP`. The certificate becomes `ACTIVE` 15 to 60 minutes after DNS propagates.

```bash
echo "DNS A record: ${DOMAIN} -> ${LB_IP}"

# Repeat until the status is ACTIVE
gcloud compute ssl-certificates describe cert-ip-jor-mcp --global \
  --format='value(managed.status, managed.domainStatus)'
```

Reference: [`ssl-certificates describe`](https://cloud.google.com/sdk/gcloud/reference/compute/ssl-certificates/describe) · [Google-managed SSL certificates](https://cloud.google.com/load-balancing/docs/ssl-certificates/google-managed-certs)

## Step 10 – Allow-list

Each authorized user is a document in the `allowed_users` collection: the document ID is the lowercase Google email, `status` must be `active` and `tier` is `basic` or `pro`.

```bash
EMAIL="journalist@example.org"   # document IDs are always lowercase (see deployment-guide.md §5.1)
# URL-encode the ID: the local part may contain characters that are not path-safe
DOC_ID="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1].lower(), safe=""))' "$EMAIL")"
curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "x-goog-user-project: $PROJECT_ID" \
  -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/(default)/documents/allowed_users?documentId=${DOC_ID}" \
  -d '{"fields":{"status":{"stringValue":"active"},"tier":{"stringValue":"basic"}}}'
```

Reference: [Firestore REST `documents.createDocument`](https://firebase.google.com/docs/firestore/reference/rest/v1/projects.databases.documents/createDocument)
