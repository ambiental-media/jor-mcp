<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


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

## 4. Automatizando a Implantação com GitHub Actions (Replicação)

Se a sua organização está replicando o `jor-mcp` usando um fork ou um repositório clonado, você pode utilizar os workflows do GitHub Actions inclusos (`.github/workflows/`) para automatizar a compilação de suas imagens Docker e a implantação no Google Cloud Run.

### 4.1 Configurando Segredos do Repositório
Para habilitar os workflows de implantação no seu repositório, navegue até **Settings > Secrets and variables > Actions** no seu repositório do GitHub e defina os seguintes segredos:

| Nome do Segredo | Descrição | Exemplo / Recurso |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | Chave JSON de uma Conta de Serviço do GCP com permissões para gravar no Artifact Registry e implantar no Cloud Run. | *(Obrigatório)* |
| `GCP_PROJECT_ID` | O ID do seu projeto no Google Cloud. | `meu-projeto-mcp-123` |
| `GCP_PROJECT_NUMBER` | O número do seu projeto no Google Cloud (usado nas anotações do serviço Knative). | `959918358302` |

### 4.2 Workflows Disponíveis
Nosso repositório contém workflows pré-configurados que você pode adaptar:
*   **`ci.yml`**: Compila, executa testes, realiza varreduras de segurança e constrói/envia o container para o seu próprio Google Artifact Registry.
*   **`cd.yml`**: Dispara um fluxo de implantação manual via `workflow_dispatch` do GitHub (permitindo que você selecione exatamente qual tag de imagem deseja implantar no Cloud Run, sem fazer deploy automático de cada merge).

Para obter a documentação detalhada sobre os critérios de teste internos, mecanismos de versionamento e detalhes de cada job da pipeline, consulte o **[Guia de Contribuição](../../../CONTRIBUTING.md#continuous-integration-ci)**.

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
