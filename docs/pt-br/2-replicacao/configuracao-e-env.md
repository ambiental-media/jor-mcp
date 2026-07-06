<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Configuração e Variáveis de Ambiente

Este documento fornece uma lista abrangente de todas as variáveis de ambiente e recursos de nuvem utilizados pelo servidor Jor-MCP. Se você estiver replicando o servidor para sua própria redação, use este guia para configurar seus arquivos `.env` e as configurações de serviço do Google Cloud.

---

## 1. Principais Recursos de Nuvem Utilizados

O Jor-MCP foi projetado como uma plataforma totalmente serverless no **Google Cloud Platform (GCP)**. Os seguintes recursos principais devem ser configurados:

1.  **Google Cloud Run:** Hospeda o servidor ASGI Python `jor-mcp` baseado em containers de forma stateless.
2.  **Google Cloud Storage (GCS):** Hospeda os ativos estáticos do portal de consentimento Next.js (`jor-mcp-site`).
3.  **Google Cloud Firestore:** Banco de dados de documentos NoSQL utilizado no modo Datastore. Ele armazena limites de taxa mensais, clientes OAuth registrados dinamicamente (DCR) e códigos de autorização temporários.
4.  **Google Cloud Identity Platform / Firebase Auth:** Gerencia a autenticação Google SSO e emite JSON Web Tokens (JWTs) seguros.
5.  **API REST externa do WordPress:** O site CMS de destino onde os artigos editoriais são publicados.
6.  **API REST externa do GitHub:** Repositório de destino que hospeda metadados editoriais multilíngues em arquivos JSON.

---

## 2. Referência de Variáveis de Ambiente

Configure estas variáveis nas configurações de ambiente do seu serviço Cloud Run ou nos arquivos `.env` locais.

### 2.1 Estado e Limitação de Taxa (Firestore)
*   `FIRESTORE_DATABASE_ID` (Padrão: `"(default)"`): O ID do banco de dados Firestore. Substitua se utilizar uma instância de banco de dados nomeada.
*   `RATE_LIMIT_COLLECTION` (Padrão: `"rate_limits"`): Coleção do Firestore contendo janelas mensais de contadores de usuários.
*   `RATE_LIMIT_BASIC_REQUESTS` (Padrão: `"500"`): Cota mensal para usuários do nível `basic`.
*   `RATE_LIMIT_PRO_REQUESTS` (Padrão: `"2000"`): Cota mensal para usuários do nível `pro`.

### 2.2 Segurança e Proxy OAuth 2.1
*   `CORS_ALLOWED_ORIGINS` (Padrão: `"http://localhost:3000,https://jormcp.ambiental.media"`): Lista de origens permitidas (CORS) separadas por vírgula.
*   `OAUTH_SERVER_BASE_URL` (Padrão: `"https://jormcp.ambiental.media"`): URL pública deste servidor. Utilizado para metadados de descoberta.
*   `OAUTH_PORTAL_BASE_URL` (Padrão: `"https://jormcp.ambiental.media"`): URL pública do portal Next.js.
*   `OAUTH_CLIENTS_COLLECTION` (Padrão: `"oauth_clients"`): Coleção do Firestore que armazena clientes registrados.
*   `OAUTH_CODES_COLLECTION` (Padrão: `"oauth_codes"`): Coleção do Firestore que armazena códigos OAuth temporários e estado PKCE.
*   `OAUTH_CODE_TTL_SECONDS` (Padrão: `"600"`): Tempo de vida dos códigos de autorização emitidos.
*   `ALLOWED_USERS_COLLECTION` (Padrão: `"allowed_users"`): Lista branca no Firestore contendo e-mails autorizados.
*   `FIREBASE_WEB_API_KEY` (Obrigatório em produção): A Web API Key encontrada nas configurações do seu projeto Firebase, usada para a troca segura de tokens.

### 2.3 Configurações de Fontes de Conteúdo Externas
*   `WORDPRESS_API_URL` (Padrão: `"https://ambiental.media/wp-json"`): URL base da API do CMS WordPress de destino.
*   `MCP_GITHUB_TOKEN` (Opcional para repositórios públicos, recomendado): Token de Acesso Pessoal (PAT) para autenticação na API do GitHub.
*   `MCP_GITHUB_REPOS` (Obrigatório): Lista de repositórios do GitHub separados por vírgula (no formato `proprietario/repositorio`).
*   `MCP_GITHUB_API_BASE_URL` (Padrão: `"https://api.github.com"`): Endpoint da API REST do GitHub.

### 2.4 Diagnóstico e Telemetria
*   `HTTP_TIMEOUT` (Padrão: `"10.0"`): Limite de tempo de solicitações HTTP de saída em segundos.
*   `OTEL_EXPORTER_OTLP_ENDPOINT` (Opcional): Endpoint do coletor para rastreamentos OTLP.
*   `OTEL_SERVICE_NAME` (Padrão: `"jor-mcp"`): Nome do serviço registrado nos rastreamentos.
*   `GCP_PROJECT_ID` (Obrigatório para integração de rastreamento): ID do projeto GCP para vincular rastreamentos ao Cloud Logging.

---

## 3. Nota sobre a Replicação da Infraestrutura (Playbook Futuro)

Atualmente, os recursos de infraestrutura do GCP (Load Balancers, Cloud Run, coleções do Firestore e Identity Platform) são provisionados manualmente.

**Atualização Planejada:** Após a conclusão da fase inicial de replicação piloto, entregaremos um **playbook de replicação abrangente**. Isso incluirá:
*   **Infraestrutura como Código (IaC):** Scripts do Terraform para provisionar automaticamente todos os recursos necessários no GCP.
*   **Configuração como Código (CaC):** Configurações automatizadas para vincular com segurança o Identity Platform, regras do Firestore e implantação automatizada de segredos.
