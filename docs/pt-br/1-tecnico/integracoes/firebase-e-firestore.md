<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Integração Firebase e Firestore

O `jor-mcp` usa o Google Cloud para três coisas: **autenticar usuários** (Firebase Auth), **guardar o estado do OAuth** (Firestore) e **contar requisições para os limites de uso** (Firestore). As fontes de conteúdo (WordPress e GitHub) não passam pelo Google.

Por isso, o servidor precisa de um projeto Google Cloud com Firebase Auth e Firestore ativados **mesmo quando roda localmente**.

## 1. Inicialização (`src/server.py`)

Quando o servidor sobe, o *lifespan*:

*   chama `firebase_admin.initialize_app()` sem argumentos, usando as credenciais padrão do ambiente (a conta de serviço no Cloud Run; `gcloud auth application-default login` na máquina de desenvolvimento);
*   cria um único `FirestoreAsyncClient(database=FIRESTORE_DATABASE_ID)`, compartilhado pelo resto do código por meio de `get_firestore_client()`.

## 2. Firebase Auth: quem pode chamar as ferramentas (`src/middleware/auth.py`)

O `AuthMiddleware` intercepta **todas** as requisições ao endpoint MCP:

*   lê o cabeçalho `Authorization: Bearer <token>`;
*   valida o token com `auth.verify_id_token(...)`, aceitando até 60 segundos de diferença de relógio;
*   extrai o `uid` e a claim `tier` (`basic` ou `pro`; vale `basic` quando ausente) e repassa os dois ao limitador de uso;
*   se o token faltar ou for inválido, responde **401** com `WWW-Authenticate: Bearer resource_metadata=...`. É esse cabeçalho que faz o Claude Desktop abrir o navegador para o login.

Só `/health`, `/.well-known/*` e `/api/oauth/*` ficam fora dessa verificação.

## 3. Proxy OAuth 2.1 (`src/api/oauth.py`)

Clientes MCP como o Claude Desktop falam OAuth, não Firebase. O servidor faz a ponte entre os dois:

| Etapa | Endpoint | Uso do Google |
|---|---|---|
| Descoberta | `GET /.well-known/oauth-*` | nenhum (só metadados) |
| Registro do cliente (DCR) | `POST /api/oauth/register` | grava na coleção **`oauth_clients`** |
| Consentimento | portal Next.js separado (`jor-mcp-site`) | login Google SSO pelo Firebase no navegador |
| Aprovação | `POST /api/oauth/approve` | valida o token Firebase do portal, consulta **`allowed_users`** e grava o código e o desafio PKCE em **`oauth_codes`** (validade de 10 minutos) |
| Troca do código | `POST /api/oauth/token` | lê e **apaga** o código (impede reuso), confere o PKCE S256, cria um *custom token* com `auth.create_custom_token(uid)` e o troca por ID token e refresh token na **Identity Toolkit API** (`accounts:signInWithCustomToken`) |
| Renovação | `POST /api/oauth/token` (`refresh_token`) | **Secure Token API** (`securetoken.googleapis.com`) |

A lista de usuários autorizados é a coleção `allowed_users`: o ID de cada documento é um e-mail em minúsculas, e o acesso só é liberado se `status == "active"`. Ela é mantida manualmente (por exemplo, no console do Firebase).

## 4. Firestore: limites de uso

Os dois contadores usam janela fixa e `firestore.Increment(1)` atômico, o que permite que várias instâncias do Cloud Run compartilhem a mesma contagem.

*   **Por usuário** (`src/middleware/rate_limit.py`): coleção `rate_limits`, um documento por `{uid}_{AAAA-MM}`. Cota mensal de 500 requisições no tier `basic` e 2000 no `pro` (`RATE_LIMIT_BASIC_REQUESTS`, `RATE_LIMIT_PRO_REQUESTS`). Acima da cota, o servidor responde **429** com `Retry-After` até o início do mês seguinte.
*   **Por IP** (`src/middleware/ip_rate_limit.py`): coleção `ip_rate_limits`. Vale só para as rotas não autenticadas (`/api/oauth/*` e `/.well-known/*`) e impede que alguém encha o Firestore de registros DCR. O padrão é 60 requisições por minuto. Os documentos têm um campo `expires_at`, pensado para uma política de TTL do Firestore.

Os dois limitadores **deixam passar** (*fail open*) se o Firestore der erro. Uma falha no banco não derruba o serviço, mas os limites deixam de valer enquanto ela durar.

## 5. Resumo das coleções

| Coleção | Conteúdo |
|---|---|
| `allowed_users` | lista de e-mails autorizados |
| `oauth_clients` | clientes MCP registrados |
| `oauth_codes` | códigos de autorização temporários com PKCE |
| `rate_limits` | contadores mensais por usuário |
| `ip_rate_limits` | contadores por IP, por minuto |

Os nomes das coleções podem ser alterados por variáveis de ambiente; veja [Configuração e Variáveis de Ambiente](../../2-replicacao/configuracao-e-env.md).

## 6. Notas de operação

*   **O modo nativo é obrigatório.** O código usa o cliente nativo do Firestore (`google.cloud.firestore_v1`), que não funciona com um banco em modo Datastore.
*   **Liberar acesso a um usuário:** crie um documento em `allowed_users` cujo ID seja o e-mail do usuário em minúsculas, com o campo `status: "active"`.
*   **Dar o tier `pro`:** o tier vem de uma *custom claim* do Firebase. Defina-a com o Admin SDK, por exemplo `auth.set_custom_user_claims(uid, {"tier": "pro"})`. Este repositório não automatiza essa etapa.

## Decisão Arquitetural: Por que Estado Serverless?
Contamos com o Firestore em vez de um cache em memória ou uma instância Redis provisionada para manter a ausência de estado (statelessness) nos contêineres do Cloud Run. Isso permite escalonamento horizontal a zero, maximizando a eficiência de FinOps enquanto evita burlar o limite de taxa durante picos de tráfego.