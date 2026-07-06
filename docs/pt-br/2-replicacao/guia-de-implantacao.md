<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Guia de Infraestrutura e Implantação

Este documento descreve a arquitetura de implantação do servidor Jor-MCP no Google Cloud Platform (GCP).

---

## 1. Visão Geral da Arquitetura GCP

O sistema foi projetado para ser totalmente serverless, altamente disponível e stateless na camada de aplicação.

*   **Ponto de Entrada (Entrypoint):** Load Balancer de Aplicação Externo Global (Gerencia domínios personalizados, SSL e streaming SSE). [Consulte o guia de configuração detalhado](configuracao-load-balancer.md).
*   **Hospedagem Frontend:** Google Cloud Storage (GCS) Bucket configurado como Backend Bucket no Load Balancer, com Cloud CDN ativado.
*   **Camada de Computação:** Google Cloud Run (Containerizado, auto-scaling). Bloqueado para "Tráfego interno e de Load Balancer apenas."
*   **Banco de Dados/Estado:** Google Cloud Firestore (Gerencia limites de taxa distribuídos, clientes OAuth DCR e códigos autorizativos).
*   **Identidade:** Google Cloud Identity Platform / Firebase Auth (Valida tokens JWT).
*   **Observabilidade:** Google Cloud Operations Suite (Cloud Logging e Cloud Trace via OpenTelemetry).

---

## 2. Variáveis de Ambiente e Recursos

O servidor depende estritamente de variáveis de ambiente para configuração. Nenhum segredo é codificado diretamente. No GCP, estes segredos são injetados de forma segura a partir do Google Secret Manager no Cloud Run.

Para uma lista detalhada e abrangente de todas as variáveis de ambiente e recursos de nuvem, consulte o **[Guia de Configuração e Ambiente](configuracao-e-env.md)**.

> **Nota sobre Roteamento:** Certifique-se de que seu Load Balancer Global esteja configurado para rotear o tráfego destinado a `/mcp/*` e `/api/oauth/*` para o Serverless NEG (serviço Cloud Run), e todo o outro tráfego (`/*`) para o Backend Bucket (GCS).

---

## 3. Estratégia de Dockerização

Usamos um `Dockerfile` de múltiplos estágios para manter a imagem de produção leve e segura:

1.  **Estágio Builder:** Utiliza o gerenciador de pacotes `uv` para resolver e instalar dependências em um ambiente virtual isolado (`.venv`).
2.  **Estágio Runtime:** Copia apenas o `.venv` e o diretório `src/` para uma imagem base leve Python. Executa a aplicação como um usuário não root (`appuser`) para cumprir as melhores práticas de segurança de contêineres.

---

## 4. Automatizando a Implantação com GitHub Actions (Replicação)

Se sua organização está replicando o `jor-mcp` usando um fork ou repositório clonado, você pode utilizar os workflows integrados do GitHub Actions (`.github/workflows/`) para automatizar as compilações de suas imagens Docker e as implantações no Google Cloud Run.

### 4.1 Configurando Segredos do Repositório
Para habilitar os workflows de implantação no seu repositório, navegue até **Settings > Secrets and variables > Actions** no GitHub e defina os seguintes segredos:

| Nome do Segredo | Descrição | Exemplo / Recurso |
| :--- | :--- | :--- |
| `GCP_SA_KEY` | Chave JSON de uma Conta de Serviço do GCP com permissões para gravar no Artifact Registry e implantar no Cloud Run. | *(Obrigatório)* |
| `GCP_PROJECT_ID` | O ID do seu projeto no Google Cloud. | `meu-projeto-mcp-123` |
| `GCP_PROJECT_NUMBER` | O número do seu projeto no Google Cloud (usado nas anotações do serviço Knative). | `959918358302` |

### 4.2 Workflows Disponíveis
Nosso repositório contém workflows pré-configurados que você pode adaptar:
*   **`ci.yml`**: Compila, executa testes, realiza varreduras de segurança e constrói/envia o container para o seu próprio Google Artifact Registry.
*   **`cd.yml`**: Dispara um fluxo de implantação manual via `workflow_dispatch` do GitHub (permitindo que você selecione exatamente qual tag de imagem deseja implantar no Cloud Run, sem fazer deploy automático de cada merge).

Para obter a documentação detalhada sobre os critérios de teste internos, mecanismos de versionamento e detalhes de cada job da pipeline, consulte o **[Guia de Contribuição](../../../CONTRIBUTING_pt-br.md#integracao-continua-ci)**.

---

## 5. Manifesto de Serviço Declarativo

O serviço Cloud Run é gerenciado de forma declarativa através do arquivo `service.yaml` na raiz do repositório. Este arquivo é a única fonte de verdade para as especificações do serviço.

Variáveis sensíveis nunca são codificadas diretamente no YAML. Elas são armazenadas no GCP Secret Manager e injetadas diretamente no container em tempo de execução via `valueFrom: secretKeyRef`.

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
