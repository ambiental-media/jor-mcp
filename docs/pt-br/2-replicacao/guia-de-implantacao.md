<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Guia de Infraestrutura e Implantação

Este documento descreve a arquitetura de implantação do servidor Jor-MCP no Google Cloud Platform (GCP), permissões de conta de serviço GCP, configurações de segurança do painel Firebase Authentication e gerenciamento da lista de usuários autorizados no Firestore.

> Para os comandos `gcloud` de provisionamento passo a passo, veja o [Guia de Provisionamento GCP](provisionamento-gcp.md).

---

## 1. Visão Geral da Arquitetura GCP

O sistema foi projetado para ser totalmente serverless, altamente disponível e stateless na camada de aplicação.

*   **Ponto de Entrada (Entrypoint):** Load Balancer de Aplicação Externo Global (Gerencia domínios personalizados, SSL e streaming SSE). [Consulte o guia de configuração detalhado](configuracao-load-balancer.md).
*   **Hospedagem Frontend:** Google Cloud Storage (GCS) Bucket configurado como Backend Bucket no Load Balancer, com Cloud CDN ativado.
*   **Camada de Computação:** Google Cloud Run (Containerizado, auto-scaling). Bloqueado para "Tráfego interno e de Load Balancer apenas." O serviço é configurado para **permitir invocações não autenticadas** (binding IAM `roles/run.invoker` para `allUsers`), pois o load balancer encaminha HTTP puro; identidade e autorização são validadas exclusivamente na camada de aplicação (JWT do Firebase + allow-list).
*   **Banco de Dados/Estado:** Google Cloud Firestore (Gerencia limites de taxa distribuídos, clientes OAuth DCR e códigos autorizativos).
*   **Identidade:** Google Cloud Identity Platform / Firebase Auth (Valida tokens JWT).
*   **Observabilidade:** Google Cloud Operations Suite (Cloud Logging e Cloud Trace via OpenTelemetry).

---

## 2. Permissões de Conta de Serviço GCP IAM

O Cloud Run atribui a Conta de Serviço padrão do Compute a um serviço, a menos
que seja instruído de outra forma. Essa conta possui a permissão ampla de
`Editor`, então um container comprometido ganharia controle sobre todos os
recursos do projeto. Crie uma conta de serviço dedicada e de menor privilégio
para o serviço Cloud Run.

Nesta implantação de referência, a identidade de execução é
`jor-mcp-runner@<project-id>.iam.gserviceaccount.com`.

### 2.1 Criando a conta de serviço

```bash
gcloud iam service-accounts create jor-mcp-runner \
  --project "<project-id>" \
  --display-name="Jor-MCP Cloud Run Runtime" \
  --description="Dedicated runtime identity for the jor-mcp-server Cloud Run service"
```

### 2.2 Funções IAM necessárias

Atribua apenas as permissões que a aplicação realmente utiliza em execução. As
cinco funções de infraestrutura cobrem Firestore, segredos e observabilidade; as
duas funções de autenticação são necessárias porque o servidor usa o Firebase
Admin SDK para mais do que validar JWT (`src/api/oauth.py`).

| Função | Escopo | Por que é necessária |
| :--- | :--- | :--- |
| `roles/datastore.user` | Projeto | Ler e gravar registros de limite de taxa, clientes OAuth e códigos temporários no Firestore. |
| `roles/secretmanager.secretAccessor` | Projeto | Decodificar os segredos injetados no container na inicialização (`MCP_GITHUB_TOKEN`, `JWT_SECRET`). |
| `roles/cloudtrace.agent` | Projeto | Permitir que o OpenTelemetry exporte rastreamentos de latência para o Cloud Trace. |
| `roles/logging.logWriter` | Projeto | Enviar os logs da aplicação para o Cloud Logging. |
| `roles/monitoring.metricWriter` | Projeto | Exportar métricas do serviço para o Cloud Monitoring. |
| `roles/firebaseauth.admin` | Projeto | Buscar usuários (`auth.get_user`) e revogar refresh tokens (`auth.revoke_refresh_tokens`) durante o fluxo de refresh do OAuth. |
| `roles/iam.serviceAccountTokenCreator` | SA de execução (nela mesma) | Assinar tokens customizados do Firebase (`auth.create_custom_token`). No Cloud Run o Admin SDK não tem chave de assinatura local, então assina pela API IAM `signBlob` na própria conta de serviço de execução. |

```bash
RUNNER="serviceAccount:jor-mcp-runner@<project-id>.iam.gserviceaccount.com"

for ROLE in \
  roles/datastore.user \
  roles/secretmanager.secretAccessor \
  roles/cloudtrace.agent \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/firebaseauth.admin
do
  gcloud projects add-iam-policy-binding "<project-id>" \
    --member="$RUNNER" --role="$ROLE" --condition=None
done

# Restrita à própria conta de serviço de execução: a permissão signBlob só é
# necessária nessa conta, então mantenha-a fora do projeto.
gcloud iam service-accounts add-iam-policy-binding \
  jor-mcp-runner@<project-id>.iam.gserviceaccount.com \
  --project "<project-id>" \
  --member="$RUNNER" \
  --role="roles/iam.serviceAccountTokenCreator"
```

Nenhuma permissão do Artifact Registry é necessária: o Cloud Run baixa a imagem
do container com o próprio agente de serviço, não com a conta de serviço de
execução. A validação de JWT do Firebase (`auth.verify_id_token`) também não
exige permissão IAM — ela utiliza certificados públicos de assinatura obtidos
via HTTPS. As demais operações do Firebase Admin SDK acima exigem funções: a
assinatura de tokens customizados usa a API IAM `signBlob`, e a busca de usuários
/ revogação de refresh tokens usam as permissões de administrador do Firebase
Auth. A chamada `signBlob` requer o escopo OAuth `cloud-platform`, que o Cloud
Run concede por padrão.

> **Ordem de execução:** crie a conta na seção 2.1 primeiro, depois execute os
> dois blocos de comando acima.

### 2.3 Vinculando a conta ao serviço

A identidade de execução é declarada no `service.yaml` e aplicada a cada deploy.
O projeto da conta é substituído a partir de `${GCP_PROJECT_ID}` pelo `envsubst`:

```yaml
spec:
  template:
    spec:
      serviceAccountName: jor-mcp-runner@${GCP_PROJECT_ID}.iam.gserviceaccount.com
```

### 2.4 Identidade de execução vs. identidade de implantação

São duas contas distintas e não devem ser confundidas:

* **Identidade de execução** (`jor-mcp-runner`) — a conta sob a qual o container
  é executado. Precisa das permissões listadas acima e de nenhuma permissão de
  implantação.
* **Identidade de implantação** — a conta com a qual o pipeline de CI/CD se
  autentica (veja `GCP_SA_KEY` na seção 8.1). Precisa de permissão para enviar
  imagens ao Artifact Registry e implantar no Cloud Run.

A identidade de implantação também precisa da permissão
`roles/iam.serviceAccountUser` sobre a conta de serviço de execução, caso
contrário o `gcloud run services replace` falha com `iam.serviceaccounts.actAs`.
O mesmo vale para qualquer operador humano que execute um deploy manual:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  jor-mcp-runner@<project-id>.iam.gserviceaccount.com \
  --project "<project-id>" \
  --member="serviceAccount:<deployer-sa>@<project-id>.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

---

## 3. Configuração de Segurança no Console Firebase Authentication

Como o fluxo de consentimento do Jor-MCP utiliza o Google SSO para verificar a identidade dos usuários, você deve configurar o console do Firebase / Google Cloud Identity Platform para impedir cadastros não autorizados.

### 3.1 Desativação de Auto-Cadastro
Por padrão, qualquer pessoa com uma conta do Google pode se autenticar no seu aplicativo Firebase, criando uma conta de usuário. Você deve desativar essa criação automática de contas para proteger o sistema:
1.  Acesse o **Console do Firebase** e selecione o seu projeto.
2.  Navegue até **Authentication > Settings > User actions** (ou Configurações > Ações do Usuário).
3.  Desmarque a opção **"Enable create (sign-up)"** (ou **"Permitir criação de contas"**).
4.  Salve as alterações. Isso garante que apenas contas previamente cadastradas ou que correspondam a registros permitidos consigam logar, embora o Google SSO ainda funcione normalmente para verificar a identidade de usuários válidos já cadastrados.

### 3.2 Desativar Provedor de Email e Senha
Para evitar ataques de força bruta, tentativas de roubo de credenciais ou desvio do Google SSO:
1.  No **Console do Firebase**, acesse **Authentication > Sign-in method** (Método de login).
2.  Selecione **E-mail/senha** e clique em **Desativar** (ou mude a chave de status para desligado).
3.  Garanta que o provedor **Google** seja o único ativo.

---

## 4. Compreendendo o Caráter Não Secreto das Chaves do Firebase

É um equívoco comum pensar que o objeto `firebaseConfig` (contendo `apiKey`, `authDomain`, `projectId`, etc.) deve ser mantido sob sigilo absoluto.

### Por que a API Key é Pública
No Firebase, a `apiKey` atua como um **identificador público do projeto**, e não como uma chave mestra ou credencial de administrador. Ela é incorporada diretamente no código do lado do cliente (o front-end do portal) para permitir a conexão do navegador com os serviços do Google. Como ela é pública por padrão, você não protegerá o seu banco de dados tentando escondê-la.

### Como Proteger o Seu Sistema
A segurança do seu app **não depende** de ocultar a `apiKey`. Em vez disso, reforce-a através de:
1.  **Restrições da API Key no GCP:** No Console do Google Cloud, navegue até **APIs e Serviços > Credenciais**, localize a API Key do Firebase e configure restrições de uso para aceitar conexões apenas a partir do domínio oficial do seu portal (ex: `https://jormcp.ambiental.media`).
2.  **Regras de Segurança do Firestore (Security Rules):** Garanta que o seu banco de dados NoSQL esteja devidamente travado para que clientes consigam ler/escrever apenas nos diretórios que possuem permissão explícita. Por exemplo, recuse acesso geral de gravação para as coleções `allowed_users` ou `oauth_clients`.

---

## 5. Gerenciamento Manual da Lista Branca (`allowed_users`)

O Jor-MCP impõe o controle de acesso por meio de uma lista de e-mails autorizados (whitelist) persistida no Firestore.

Para autorizar um novo jornalista ou parceiro a utilizar o servidor MCP, um administrador do projeto precisa adicionar manualmente o e-mail correspondente à coleção `allowed_users` no Firestore.

### 5.1 Formato do Documento da Whitelist
Adicione um documento na coleção `allowed_users` respeitando os seguintes campos:
*   **ID do Documento:** Deve ser obrigatoriamente o e-mail Google do usuário formatado em **letras minúsculas** (ex: `usuario@dominio.com`). Isso garante que as buscas sejam case-insensitive.
*   **Campos do Documento:**
    *   `status` (String): Deve ser definido como `"active"` para permitir o acesso. Caso seja definido como `"disabled"` ou qualquer outro valor, o acesso será rejeitado.
    *   `tier` (String, **Obrigatório**): A role do usuário. Deve ser `"basic"` ou `"pro"` — determina a cota de limite de taxa mensal. **Um usuário sem `tier` (ou com um valor fora desses dois) não consegue concluir o consentimento e recebe `403` em todas as chamadas ao servidor MCP.** A atribuição da role é manual e faz parte do cadastro.

> **Propagação e revogação:** a role é espelhada na custom claim `tier` do usuário no Firebase Auth no momento do consentimento e reconferida a cada renovação de token. Alterar o `tier`, definir `status: "disabled"` ou remover o documento passa a valer em até uma hora — o tempo de vida do ID token emitido — sem qualquer ação do usuário. Quem perde a autorização tem os refresh tokens revogados na renovação seguinte, o que encerra o acesso em vez de apenas negar aquela requisição.

---

## 6. Variáveis de Ambiente e Recursos

O servidor depende estritamente de variáveis de ambiente para configuração. Nenhum segredo é codificado diretamente. No GCP, estes segredos são injetados de forma segura a partir do Google Secret Manager no Cloud Run.

Para uma lista detalhada e abrangente de todas as variáveis de ambiente e recursos de nuvem, consulte o **[Guia de Configuração e Ambiente](configuracao-e-env.md)**.

> **Nota sobre Roteamento:** Certifique-se de que seu Load Balancer Global esteja configurado para rotear o tráfego destinado a `/mcp/*` e `/api/oauth/*` para o Serverless NEG (serviço Cloud Run), e todo o outro tráfego (`/*`) para o Backend Bucket (GCS).

---

## 7. Estratégia de Dockerização

Usamos um `Dockerfile` de múltiplos estágios para manter a imagem de produção leve e segura:

1.  **Estágio Builder:** Utiliza o gerenciador de pacotes `uv` para resolver e instalar dependências em um ambiente virtual isolado (`.venv`).
2.  **Estágio Runtime:** Copia apenas o `.venv` e o diretório `src/` para uma imagem base leve Python. Executa a aplicação como um usuário não root (`appuser`) para cumprir as melhores práticas de segurança de contêineres.

---

## 8. Automatizando a Implantação com GitHub Actions (Replicação)

Se sua organização está replicando o `jor-mcp` usando um fork ou repositório clonado, você pode utilizar os workflows integrados do GitHub Actions (`.github/workflows/`) para automatizar as compilações de suas imagens Docker e as implantações no Google Cloud Run.

### 8.1 Configurando Variáveis e Segredos do Repositório
Para habilitar os workflows de implantação no seu repositório, navegue até **Settings > Secrets and variables > Actions** no GitHub. Os workflows leem os destinos de deploy das **variáveis** do repositório, então um fork faz deploy no próprio projeto sem editar nenhum arquivo.

| Tipo | Nome | Descrição | Exemplo |
| :--- | :--- | :--- | :--- |
| Secret | `GCP_SA_KEY` | Chave JSON da conta de serviço de deploy, codificada em base64 (veja o [Guia de Provisionamento GCP](provisionamento-gcp.md) passo 3). | *(Obrigatório)* |
| Variable | `GCP_PROJECT_ID` | O ID do seu projeto no Google Cloud. | `meu-projeto-mcp-123` |
| Variable | `GCP_PROJECT_NUMBER` | O número do seu projeto no Google Cloud (usado nas anotações do serviço Knative). | `959918358302` |
| Variable | `GCP_REGION` | Região do serviço Cloud Run e do repositório Artifact Registry. | `us-central1` |
| Variable | `GCP_AR_REPO` | Nome do repositório no Artifact Registry. | `jor-mcp` |
| Variable | `GCP_IMAGE_NAME` | Nome da imagem; deve ser igual ao `metadata.name` do `service.yaml`. | `jor-mcp-server` |
| Variable | `FIREBASE_PROJECT_ID` | Projeto do Firebase / Identity Platform. | `meu-projeto-mcp-123` |
| Variable | `WORDPRESS_API_URL` | URL base da API REST do WordPress. | `https://example.org/wp-json` |
| Variable | `MCP_GITHUB_REPOS` | Lista de `owner/repo` separada por vírgulas. | `org/repo-a,org/repo-b` |
| Variable | `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint do coletor OTLP. Deixe vazio, a menos que você rode um. | *(vazio)* |
| Variable | `FIREBASE_WEB_API_KEY` | Chave Web API do Firebase usada na troca de tokens. | `AIza...` |

### 8.2 Workflows Disponíveis
Nosso repositório contém workflows pré-configurados que você pode adaptar:
*   **`ci.yml`**: Compila, executa testes, realiza varreduras de segurança e constrói/envia o container para o seu próprio Google Artifact Registry.
*   **`cd.yml`**: Dispara um fluxo de implantação manual via `workflow_dispatch` do GitHub (permitindo que você selecione exatamente qual tag de imagem deseja implantar no Cloud Run, sem fazer deploy automático de cada merge).

Para obter a documentação detalhada sobre os critérios de teste internos, mecanismos de versionamento e detalhes de cada job da pipeline, consulte o **[Guia de Contribuição](../../../CONTRIBUTING_pt-br.md#integracao-continua-ci)**.

---

## 9. Manifesto de Serviço Declarativo

O serviço Cloud Run é gerenciado de forma declarativa através do arquivo `service.yaml` na raiz do repositório. Este arquivo é a única fonte de verdade para as especificações do serviço.

Variáveis sensíveis nunca são codificadas diretamente no YAML. Elas são armazenadas no GCP Secret Manager e injetadas diretamente no container em tempo de execução via `valueFrom: secretKeyRef`.

### Aplicando o manifesto localmente

Exporte as variáveis de ambiente necessárias e use `envsubst` para substituir os placeholders antes de aplicar:

```bash
export IMAGE_URL="us-central1-docker.pkg.dev/jor-mcp/jor-mcp/jor-mcp-server:SHA"
export GCP_PROJECT_NUMBER="959918358302"
export GCP_PROJECT_ID="jor-mcp"
export GCP_REGION="us-central1"
export FIREBASE_PROJECT_ID="..."
export WORDPRESS_API_URL="..."
export MCP_GITHUB_REPOS="..."
export OTEL_EXPORTER_OTLP_ENDPOINT="..."
export FIREBASE_WEB_API_KEY="..."

for v in IMAGE_URL GCP_PROJECT_NUMBER GCP_PROJECT_ID GCP_REGION; do
  : "${!v:?defina $v antes de executar o envsubst}"
done

envsubst < service.yaml | gcloud run services replace - --region us-central1
```

### No pipeline de CD (GitHub Actions)

As variáveis acima são injetadas automaticamente a partir das variáveis do repositório. O comando `envsubst` é executado pelo pipeline antes de chamar `gcloud run services replace`, portanto, nenhuma substituição manual é necessária.

Após o `gcloud run services replace`, o pipeline também aplica o binding `roles/run.invoker` para `allUsers`, garantindo o estado sem autenticação em cada deploy.
