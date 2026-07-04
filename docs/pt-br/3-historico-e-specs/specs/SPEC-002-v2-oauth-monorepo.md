# SPEC-002: Estratégia de Implementação do OAuth 2.1

## 1. Objetivo
Transição do `jor-mcp` de um Servidor de Recursos básico para um Proxy Defensivo OAuth 2.1, desacoplando a interface de consentimento do usuário para o export estático do `jor-mcp-site`.

### Critérios de Sucesso
- [ ] O Claude Desktop conclui o fluxo PKCE de 4 fases nativamente sem arquivos de configuração do usuário.
- [ ] O proxy Python normaliza corretamente incompatibilidades de `localhost` / `127.0.0.1` do DCR.
- [ ] O proxy Python emite corretamente *Access Tokens* de curta duração e *Refresh Tokens* de longa duração via Firebase Admin SDK.
- [ ] O frontend Next.js estático dispara com sucesso o endpoint de backend `/api/oauth/approve` via CORS após validar o usuário contra uma whitelist no Firestore.

## 2. Tech Stack & Infraestrutura
- **Backend:** Python 3.12, `fastmcp`, `uvicorn`, `firebase-admin`, `google-cloud-firestore`.
- **Frontend:** Next.js (Exportação Estática) hospedado em **Google Cloud Storage (GCS) Bucket** por trás do Cloud CDN, React, Firebase Auth JS SDK (apenas Google SSO).
- **Roteamento:** Global Load Balancer do GCP (`/mcp/*` e `/api/oauth/*` -> Backend Serverless NEG; `/*` -> GCS Backend Bucket).
- **Identidade:** Whitelist B2B estrita. Inscrições públicas desativadas. Administradores provisionam usuários manualmente via Console do Firebase.

## 3. Comandos (Backend Python)
- **Dev:** `uv run uvicorn src.server:app --reload`
- **Test:** `make check`
- **Lint:** `uv run ruff check . --fix`
- **Format:** `uv run ruff format .`
- **Typecheck:** `uv run mypy .`

## 4. Estrutura do Projeto
- `src/api/` -> Novo diretório para endpoints HTTP OAuth (fora do contexto FastMCP).
- `src/middleware/` -> Limitação de taxa e parsing de autenticação.
- `src/services/` -> Integrações WordPress e GitHub.

## 5. Estilo de Código & Convenções
- **Importações absolutas:** Sempre ancoradas em `src`.
- **Tipagem:** Use sintaxe nativa do Python 3.12+ (ex: `str | None`).
- **Limites:** Todos os payloads OAuth recebidos devem ser validados usando modelos Pydantic em `src/api/`.

## 6. Estratégia de Testes
- Use `pytest-asyncio`.
- Mocke o `firebase_admin` para evitar chamadas de rede.
- Use `TestClient` para verificação de endpoints HTTP OAuth.

## 7. Limites (Boundaries)
- **Sempre fazer:** Validar todos os payloads OAuth recebidos usando Pydantic. Normalizar URIs de redirecionamento para `localhost`. Impor a verificação de whitelist do Firestore tanto no frontend (`/authorize`) quanto no backend (`/api/oauth/approve`).
- **Perguntar antes:** Antes de adicionar novas dependências externas ao `pyproject.toml`. Antes de alterar os esquemas da coleção Firestore `oauth_clients`.
- **Nunca fazer:** Nunca retornar HTML puro a partir do Python; a UI permanece no portal Next.js. Nunca logar códigos de Auth brutos ou Access Tokens.

## Questões em Aberto
- Nenhuma.
