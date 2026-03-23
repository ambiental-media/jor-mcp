#!/bin/bash
set -euo pipefail

# =============================================================================
# build_push_deploy.sh
# Jor-MCP — Build, push e deploy no Google Cloud Run
# =============================================================================
# Uso:
#   ./build_push_deploy.sh
#
# Obs: as variáveis de ambiente do serviço (WP_API_URL, GITHUB_TOKEN)
# são configuradas diretamente no Cloud Run e não precisam ser passadas aqui.
# =============================================================================

# --- Configuração -------------------------------------------------------------

GCP_PROJECT_ID="jor-mcp"
GCP_REGION="us-central1"
AR_REPOSITORY="jor-mcp"
IMAGE_NAME="jor-mcp-server"
CLOUD_RUN_SERVICE="jor-mcp-server"

# --- Variáveis derivadas -----------------------------------------------------

AR_HOST="${GCP_REGION}-docker.pkg.dev"
IMAGE_TAG="${AR_HOST}/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:latest"

# --- Autenticação do Docker no Artifact Registry -----------------------------

echo ""
echo "🔐 Autenticando Docker no Artifact Registry..."
gcloud auth configure-docker "${AR_HOST}" --quiet

# --- Build -------------------------------------------------------------------

echo ""
echo "🏗️  Construindo imagem Docker..."
echo "   Tag: ${IMAGE_TAG}"
docker build --platform linux/amd64 -t "${IMAGE_TAG}" .

# --- Push --------------------------------------------------------------------

echo ""
echo "📤 Enviando imagem para o Artifact Registry..."
docker push "${IMAGE_TAG}"

# --- Deploy ------------------------------------------------------------------

echo ""
echo "🚀 Fazendo deploy no Cloud Run..."
gcloud run deploy "${CLOUD_RUN_SERVICE}" \
  --image="${IMAGE_TAG}" \
  --region="${GCP_REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --quiet

# --- Resultado ---------------------------------------------------------------

echo ""
echo "✅ Deploy concluído!"
echo ""
SERVICE_URL=$(gcloud run services describe "${CLOUD_RUN_SERVICE}" \
  --region="${GCP_REGION}" \
  --format="value(status.url)")
echo "   URL do serviço: ${SERVICE_URL}"
echo "   Health check:   ${SERVICE_URL}/health"