# Infraestrutura & Implantação

Este documento descreve a arquitetura de implantação do servidor Jor-MCP no Google Cloud Platform (GCP).

## 1. Visão Geral da Arquitetura GCP

O sistema foi projetado para ser totalmente serverless, altamente disponível e stateless na camada de aplicação.

- **Entrypoint:** Global External Application Load Balancer (Gerencia domínios personalizados, SSL e streaming SSE). [Veja o guia detalhado de configuração](configuracao-load-balancer.md).
- **Hospedagem Frontend:** Google Cloud Storage (GCS) Bucket configurado como Backend Bucket no Load Balancer, com Cloud CDN ativado.
- **Compute:** Google Cloud Run (Containerizado, auto-scaling). Bloqueado para "Internal and Cloud Load Balancing traffic only."
- **Banco de Dados/Estado:** Google Cloud Firestore (Gerencia a limitação de taxa distribuída via incrementos atômicos).
- **Identidade:** Google Cloud Identity Platform / Firebase Auth (Valida JWTs).
- **Observabilidade:** Google Cloud Operations Suite (Cloud Logging e Cloud Trace via OpenTelemetry).

## 2. Variáveis de Ambiente

O servidor depende estritamente de variáveis de ambiente para configuração. Nenhum segredo é codificado. No GCP, elas devem ser injetadas via Google Secret Manager no Cloud Run.

| Variável | Descrição | Padrão |
| :--- | :--- | :--- |
| `PORT` | A porta onde o servidor ASGI escuta. | `8080` |
| `LOG_LEVEL` | Nível de log do Python (`INFO`, `DEBUG`, `WARNING`). | `INFO` |
| `FIREBASE_PROJECT_ID` | O ID do projeto GCP associado ao Firebase Auth. | *(Obrigatório)* |
| `GCP_PROJECT_ID` | ID do projeto GCP usado para emitir `logging.googleapis.com/trace`. | *(Opcional no Cloud Run)* |
| `WORDPRESS_API_URL` | URL base para a API REST principal do WordPress. | `https://ambiental.media/wp-json/wp/v2` |
| `MCP_GITHUB_TOKEN` | Token de Acesso Pessoal para ler repositórios privados Next.js. | *(Obrigatório)* |
| `MCP_GITHUB_REPOS` | Lista de repositórios Next.js separados por vírgula. | *(Obrigatório)* |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| Endpoint OTLP para rastreamento. Vazio significa exportação para console. | `""` |

> **Nota sobre Limitação de Taxa (Firestore):** A aplicação depende do Google Cloud Firestore para seu estado. Ele utiliza automaticamente as Google Application Default Credentials (ADC) vinculadas à conta de serviço do Cloud Run. Nenhuma string de conexão ou segredo explícito é necessário, mas a conta de serviço *deve* receber a função IAM `roles/datastore.user`.
> 
> **Nota sobre Roteamento:** Certifique-se de que seu Load Balancer Global esteja configurado para rotear o tráfego destinado a `/mcp/*` e `/api/oauth/*` para o Serverless NEG (serviço Cloud Run), e todo o outro tráfego (`/*`) para o Backend Bucket (GCS).

## 3. Estratégia de Dockerização

Usamos um `Dockerfile` de múltiplos estágios para manter a imagem de produção segura e leve.

1. **Estágio Builder:** Usa o gerenciador de pacotes `uv` para resolver e instalar dependências em um ambiente virtual isolado (`.venv`).
2. **Estágio Runtime:** Copia apenas o `.venv` e o diretório `src/` para uma imagem base leve do Python. Executa a aplicação como um usuário não root (`appuser`) para cumprir as melhores práticas de segurança de containers.

## 4. Pipeline de Implantação

A implantação deve ser automatizada via GitHub Actions:
1. Disparado no push para o branch `main`.
2. Executa `make check` (Testes, Lint, checagem de tipos).
3. Constrói a imagem Docker.
4. Envia a imagem para o Google Artifact Registry.
5. Implanta a nova revisão no Cloud Run usando a conta de serviço existente.
6. Faz o upload da exportação estática do Next.js (diretório `out/`) para o bucket GCS.

## 5. Manifesto de Serviço Declarativo

O serviço Cloud Run é gerenciado declarativamente via um arquivo `service.yaml` na raiz do repositório. Este arquivo é a única fonte de verdade para a configuração do serviço.

Variáveis sensíveis (por exemplo, `MCP_GITHUB_TOKEN`) nunca são codificadas no YAML. Elas são armazenadas no GCP Secret Manager e injetadas diretamente no container em tempo de execução via `valueFrom: secretKeyRef`.

### Aplicando o manifesto localmente

Exporte as variáveis de ambiente necessárias e use `envsubst` para substituir os placeholders antes de aplicar:

```bash
export IMAGE_URL="us-central1-docker.pkg.dev/jor-mcp/jor-mcp/jor-mcp-server:SHA"
export GCP_PROJECT_NUMBER="959918358302"
export GCP_PROJECT_ID="jor-mcp"
export FIREBASE_PROJECT_ID="..."
export WORDPRESS_API_URL="..."
export MCP_GITHUB_REPOS="..."
export OTEL_EXPORTER_OTLP_ENDPOINT="..."

envsubst < service.yaml | gcloud run services replace - --region us-central1
```

### No pipeline de CD (GitHub Actions)
As variáveis acima são injetadas automaticamente como segredos e variáveis do repositório. O comando `envsubst` é executado pelo pipeline antes de chamar `gcloud run services replace`, portanto, nenhuma substituição manual é necessária.
