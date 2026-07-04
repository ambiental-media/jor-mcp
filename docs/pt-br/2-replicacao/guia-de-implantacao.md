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

## 4. Pipeline de CI/CD

O projeto usa três workflows separados do GitHub Actions. A Integração Contínua e o release/versionamento são totalmente automatizados; a implantação no Cloud Run é um passo manual e deliberado.

### 4.1 Integração Contínua — `.github/workflows/ci.yml`

Disparado em todo Pull Request. Possui três jobs independentes:

1. **`check`** — Gate de qualidade e segurança de código. Executa lint (`ruff check`), checagem de formatação (`ruff format --check`), checagem de tipos (`mypy`), testes com cobertura mínima de 90% (`pytest --cov-fail-under=90`), SAST (`bandit`) e auditoria de dependências (`pip-audit`).
2. **`build-and-push`** — Roda apenas após o `check` passar. Constrói a imagem Docker, escaneia com Trivy (falha em vulnerabilidades de biblioteca `CRITICAL` e `HIGH`) e a envia para o Artifact Registry com a tag `:pr-<NÚMERO_DO_PR>` (ex.: `:pr-44`).
3. **`commitlint`** — Verifica se ao menos um commit do PR segue o formato Conventional Commits. É isso que alimenta o versionamento automático no momento do release.

### 4.2 Release & Versionamento — `.github/workflows/release.yml`

Disparado quando um Pull Request é **mergeado na `main`**. Executa o [`python-semantic-release`](https://python-semantic-release.readthedocs.io/), que:

1. Analisa os Conventional Commits do PR mergeado e calcula a próxima versão [SemVer](https://semver.org/) (`fix` → PATCH, `feat` → MINOR, `BREAKING CHANGE` → MAJOR).
2. Atualiza o campo `version` no `pyproject.toml`, cria e envia a tag git `vX.Y.Z` e publica uma GitHub Release com notas geradas automaticamente.
3. Se (e somente se) um release foi produzido, **re-tagueia a imagem existente** — a imagem `:pr-<N>` construída durante o CI é re-tagueada no Artifact Registry para `:vX.Y.Z` e `:latest`. Nenhum rebuild acontece; o mesmo digest é promovido.

Isso significa que um PR mergeado nunca reconstrói a imagem — o artefato testado no CI é exatamente o mesmo promovido para um release versionado.

### 4.3 Continuous Deployment — `.github/workflows/cd.yml`

A implantação é **manual e intencional**, não disparada por merges. Roda via `workflow_dispatch` com um input obrigatório `image_tag` (ex.: `pr-44` ou `v1.2.0`). O workflow:

1. Verifica se a tag solicitada realmente existe no Artifact Registry (falha imediatamente caso contrário).
2. Renderiza o `service.yaml` com `envsubst`, substituindo apenas uma allowlist explícita de variáveis.
3. Implanta a imagem selecionada no Cloud Run via `gcloud run services replace`.

Como a implantação consome uma imagem existente por tag, ela é totalmente desacoplada do versionamento: você escolhe exatamente qual build chega à produção, e o passo de deploy nunca altera a versão do projeto.

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
