<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Guia de Provisionamento GCP

Comandos para provisionar a infraestrutura GCP do Jor-MCP, na ordem de execução. Antes de começar, confira os [Pré-requisitos](pre-requisitos.md).

## Passo 0 – Variáveis

Os passos seguintes usam estas variáveis. Rode todos na mesma sessão do terminal.

```bash
# --- Fill in for your newsroom ---
export PROJECT_ID="my-newsroom-mcp"
export REGION="us-central1"
export FIRESTORE_LOCATION="nam5"
export DOMAIN="mcp.example.org"
export AR_REPO="jor-mcp"
export SERVICE="jor-mcp-server"

# Point gcloud to the project
gcloud config set project "$PROJECT_ID"

# Derived values
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export RUNNER_SA="jor-mcp-runner@${PROJECT_ID}.iam.gserviceaccount.com"
export CI_SA="github-actions-ci@${PROJECT_ID}.iam.gserviceaccount.com"
```

Referência: [`gcloud config set`](https://cloud.google.com/sdk/gcloud/reference/config/set) · [`gcloud projects describe`](https://cloud.google.com/sdk/gcloud/reference/projects/describe)

## Passo 1 – APIs

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

Referência: [`gcloud services enable`](https://cloud.google.com/sdk/gcloud/reference/services/enable)

## Passo 2 – Artifact Registry

```bash
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Docker images for Jor-MCP"
```

Referência: [`gcloud artifacts repositories create`](https://cloud.google.com/sdk/gcloud/reference/artifacts/repositories/create)

## Passo 3 – Service accounts e IAM

| Service account | Função | Papéis |
| :--- | :--- | :--- |
| `jor-mcp-runner` | Conta de execução do Cloud Run | Projeto: `datastore.user`, `secretmanager.secretAccessor`, `cloudtrace.agent`, `logging.logWriter`, `monitoring.metricWriter`, `firebaseauth.admin`. Na própria SA: `iam.serviceAccountTokenCreator` |
| `github-actions-ci` | Publicação de imagens e deploy pelo GitHub Actions | Projeto: `artifactregistry.admin`, `run.admin`, `run.sourceDeveloper`, `secretmanager.secretAccessor`. Na `jor-mcp-runner`: `iam.serviceAccountUser` |

A função de cada papel de execução está descrita na seção 2 do [Guia de Implantação](guia-de-implantacao.md).

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

for ROLE in roles/artifactregistry.admin roles/run.admin roles/run.sourceDeveloper \
            roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CI_SA}" --role="$ROLE" --condition=None
done

# Allow the CI SA to deploy services that run as the runtime SA
gcloud iam service-accounts add-iam-policy-binding "$RUNNER_SA" \
  --member="serviceAccount:${CI_SA}" --role="roles/iam.serviceAccountUser"

# JSON key for GitHub Actions (base64-encoded, as the workflows expect)
gcloud iam service-accounts keys create github-actions-ci-key.json --iam-account="$CI_SA"
base64 -w0 github-actions-ci-key.json > github-actions-ci-key.b64
```

No macOS, use `base64 -i github-actions-ci-key.json > github-actions-ci-key.b64`. O conteúdo do arquivo `.b64` é o secret `GCP_SA_KEY` do repositório, descrito na seção 8 do [Guia de Implantação](guia-de-implantacao.md).

Referência: [`gcloud iam service-accounts create`](https://cloud.google.com/sdk/gcloud/reference/iam/service-accounts/create) · [`gcloud projects add-iam-policy-binding`](https://cloud.google.com/sdk/gcloud/reference/projects/add-iam-policy-binding) · [`gcloud iam service-accounts add-iam-policy-binding`](https://cloud.google.com/sdk/gcloud/reference/iam/service-accounts/add-iam-policy-binding) · [`gcloud iam service-accounts keys create`](https://cloud.google.com/sdk/gcloud/reference/iam/service-accounts/keys/create)

## Passo 4 – Secret Manager

```bash
# GitHub PAT with read access to the editorial repos
printf '%s' "ghp_xxx" | gcloud secrets create MCP_GITHUB_TOKEN \
  --replication-policy=automatic --data-file=-

# Random value
openssl rand -hex 32 | tr -d '\n' | gcloud secrets create JWT_SECRET \
  --replication-policy=automatic --data-file=-
```

Referência: [`gcloud secrets create`](https://cloud.google.com/sdk/gcloud/reference/secrets/create)

## Passo 5 – Firestore

```bash
gcloud firestore databases create \
  --database="(default)" --location="$FIRESTORE_LOCATION" --type=firestore-native

# Point-in-time recovery
gcloud firestore databases update --database="(default)" --enable-pitr

# Daily backup, kept for 98 days
gcloud firestore backups schedules create \
  --database="(default)" --recurrence=daily --retention=98d
```

Referência: [`gcloud firestore databases create`](https://cloud.google.com/sdk/gcloud/reference/firestore/databases/create) · [`gcloud firestore databases update`](https://cloud.google.com/sdk/gcloud/reference/firestore/databases/update) · [`gcloud firestore backups schedules create`](https://cloud.google.com/sdk/gcloud/reference/firestore/backups/schedules/create)

## Passo 6 – Firebase Auth

**6.1 – Adicionar o Firebase ao projeto e criar o web app**

```bash
firebase projects:addfirebase "$PROJECT_ID"
firebase apps:create WEB jor-mcp --project "$PROJECT_ID"

# Use the App ID printed above to get the web config, then copy its apiKey
firebase apps:sdkconfig WEB <APP_ID> --project "$PROJECT_ID"
export FIREBASE_WEB_API_KEY="AIza..."
```

**6.2 – No Firebase Console, em Authentication**

1. Clicar em *Get started*.
2. Em *Sign-in method*, ativar o provedor **Google** e manter **Email/Password** desativado.
3. Em *Settings → User actions*, desmarcar *Enable create (sign-up)*.

**6.3 – Domínios autorizados**

```bash
curl -sS -X PATCH \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "x-goog-user-project: $PROJECT_ID" \
  -H "Content-Type: application/json" \
  "https://identitytoolkit.googleapis.com/admin/v2/projects/${PROJECT_ID}/config?updateMask=authorizedDomains" \
  -d "{\"authorizedDomains\":[\"localhost\",\"${PROJECT_ID}.firebaseapp.com\",\"${PROJECT_ID}.web.app\",\"${DOMAIN}\"]}"
```

Referência: [Firebase CLI – comandos](https://firebase.google.com/docs/cli#command_reference) · [Login com Google (Firebase Auth)](https://firebase.google.com/docs/auth/web/google-signin) · [Identity Toolkit `projects.updateConfig`](https://cloud.google.com/identity-platform/docs/reference/rest/v2/projects/updateConfig)

## Passo 7 – Imagem e Cloud Run

Rode a partir da raiz do fork. O `service.yaml` define o serviço: ingress restrito ao Load Balancer, 0 a 5 instâncias, 1 vCPU, 1Gi e execução como `jor-mcp-runner`.

```bash
# Build and push the image
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
export IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}:latest"
docker build -t "$IMAGE_URL" .
docker push "$IMAGE_URL"

# Values injected into service.yaml
export GCP_PROJECT_ID="$PROJECT_ID"
export GCP_PROJECT_NUMBER="$PROJECT_NUMBER"
export FIREBASE_PROJECT_ID="$PROJECT_ID"
export WORDPRESS_API_URL="https://example.org/wp-json"
export MCP_GITHUB_REPOS="org/repo-a,org/repo-b"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
# FIREBASE_WEB_API_KEY was exported in step 6.1

# Render and deploy the service
envsubst '${IMAGE_URL} ${GCP_PROJECT_NUMBER} ${GCP_PROJECT_ID} ${FIREBASE_PROJECT_ID} ${WORDPRESS_API_URL} ${MCP_GITHUB_REPOS} ${OTEL_EXPORTER_OTLP_ENDPOINT} ${FIREBASE_WEB_API_KEY}' \
  < service.yaml | gcloud run services replace - --region="$REGION"

# Allow unauthenticated invocations (access is restricted by ingress and enforced by the app)
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" --member=allUsers --role=roles/run.invoker
```

Referência: [`gcloud auth configure-docker`](https://cloud.google.com/sdk/gcloud/reference/auth/configure-docker) · [`docker build`](https://docs.docker.com/reference/cli/docker/buildx/build/) · [`docker push`](https://docs.docker.com/reference/cli/docker/image/push/) · [`gcloud run services replace`](https://cloud.google.com/sdk/gcloud/reference/run/services/replace) · [`gcloud run services add-iam-policy-binding`](https://cloud.google.com/sdk/gcloud/reference/run/services/add-iam-policy-binding)

## Passo 8 – Load Balancer e Cloud Armor

```
HTTPS :443  ip-lb-jor-mcp → lb-jor-mcp-target-proxy (cert-ip-jor-mcp) → lb-jor-mcp → back-end-jor-mcp (+ Cloud Armor) → neg-cloudrun-jor-mcp → Cloud Run
HTTP  :80   ip-lb-jor-mcp-forwarding-rule → ip-lb-jor-mcp-target-proxy → ip-lb-jor-mcp-redirect (301 → HTTPS)
```

**8.1 – IP, NEG e backend service**

```bash
gcloud compute addresses create static-ip-addr-jor-mcp --global --ip-version=IPV4
export LB_IP="$(gcloud compute addresses describe static-ip-addr-jor-mcp --global --format='value(address)')"

gcloud compute network-endpoint-groups create neg-cloudrun-jor-mcp \
  --region="$REGION" --network-endpoint-type=serverless --cloud-run-service="$SERVICE"

gcloud compute backend-services create back-end-jor-mcp \
  --global --load-balancing-scheme=EXTERNAL_MANAGED --protocol=HTTPS \
  --enable-logging --logging-sample-rate=1.0
gcloud compute backend-services add-backend back-end-jor-mcp --global \
  --network-endpoint-group=neg-cloudrun-jor-mcp --network-endpoint-group-region="$REGION"
```

**8.2 – Cloud Armor (limite de 500 requisições por minuto por IP)**

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

**8.3 – URL map, certificado e frontend HTTPS**

```bash
gcloud compute url-maps create lb-jor-mcp --global --default-service=back-end-jor-mcp

gcloud compute ssl-certificates create cert-ip-jor-mcp --global --domains="$DOMAIN"

gcloud compute target-https-proxies create lb-jor-mcp-target-proxy --global \
  --url-map=lb-jor-mcp --ssl-certificates=cert-ip-jor-mcp

gcloud compute forwarding-rules create ip-lb-jor-mcp --global \
  --load-balancing-scheme=EXTERNAL_MANAGED --network-tier=PREMIUM \
  --address=static-ip-addr-jor-mcp --target-https-proxy=lb-jor-mcp-target-proxy --ports=443
```

**8.4 – Redirecionamento HTTP → HTTPS**

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

Referência: [`addresses create`](https://cloud.google.com/sdk/gcloud/reference/compute/addresses/create) · [`network-endpoint-groups create`](https://cloud.google.com/sdk/gcloud/reference/compute/network-endpoint-groups/create) · [`backend-services create`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-services/create) · [`backend-services add-backend`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-services/add-backend) · [`backend-services update`](https://cloud.google.com/sdk/gcloud/reference/compute/backend-services/update) · [`security-policies create`](https://cloud.google.com/sdk/gcloud/reference/compute/security-policies/create) · [`security-policies rules create`](https://cloud.google.com/sdk/gcloud/reference/compute/security-policies/rules/create) · [`url-maps create`](https://cloud.google.com/sdk/gcloud/reference/compute/url-maps/create) · [`url-maps import`](https://cloud.google.com/sdk/gcloud/reference/compute/url-maps/import) · [`ssl-certificates create`](https://cloud.google.com/sdk/gcloud/reference/compute/ssl-certificates/create) · [`target-https-proxies create`](https://cloud.google.com/sdk/gcloud/reference/compute/target-https-proxies/create) · [`target-http-proxies create`](https://cloud.google.com/sdk/gcloud/reference/compute/target-http-proxies/create) · [`forwarding-rules create`](https://cloud.google.com/sdk/gcloud/reference/compute/forwarding-rules/create)

## Passo 9 – DNS e certificado

Crie no seu provedor de DNS um registro `A` de `$DOMAIN` apontando para `$LB_IP`. O certificado fica `ACTIVE` entre 15 e 60 minutos depois que o DNS propaga.

```bash
echo "DNS A record: ${DOMAIN} -> ${LB_IP}"

# Repeat until the status is ACTIVE
gcloud compute ssl-certificates describe cert-ip-jor-mcp --global \
  --format='value(managed.status, managed.domainStatus)'
```

Referência: [`ssl-certificates describe`](https://cloud.google.com/sdk/gcloud/reference/compute/ssl-certificates/describe) · [Certificados SSL gerenciados pelo Google](https://cloud.google.com/load-balancing/docs/ssl-certificates/google-managed-certs)

## Passo 10 – Allow-list

Cada usuário autorizado é um documento na coleção `allowed_users`. O ID do documento é o e-mail Google em minúsculas, `status` deve ser `active` e `tier` pode ser `basic` ou `pro`.

```bash
EMAIL="journalist@example.org"
curl -sS -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/(default)/documents/allowed_users?documentId=${EMAIL}" \
  -d '{"fields":{"status":{"stringValue":"active"},"tier":{"stringValue":"basic"}}}'
```

Referência: [Firestore REST `documents.createDocument`](https://firebase.google.com/docs/firestore/reference/rest/v1/projects.databases.documents/createDocument)