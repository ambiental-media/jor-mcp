# Contratos de API & Ferramentas

## URL Base & Roteamento
O servidor Jor-MCP expõe sua interface Model Context Protocol (MCP) exclusivamente na rota `/mcp`. Todas as conexões SSE (Server-Sent Events) e trocas de mensagens JSON-RPC devem ser direcionadas para endpoints com prefixo desta rota.

*   **Endpoint SSE:** `GET /mcp/sse`
*   **Endpoint de Mensagens:** `POST /mcp/messages` (Inferido durante o handshake da conexão SSE)
*   **Verificação de Saúde (Health Check):** `GET /health` (Ignora autenticação e limitação de taxa)

---
(Nota: Embora esta documentação esteja em inglês, os campos `description` injetados nos decoradores `@mcp.tool()` no código Python devem ser escritos em português para fornecer contexto localizado aos LLMs.)

## 1. `search_content`

**Objetivo:** Pesquisa unificada de texto completo em todas as propriedades da Ambiental Media (sites WordPress e microsites Next.js).

### Parâmetros de Solicitação
| Nome | Tipo | Obrigatório | Padrão | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | **Sim** | - | A palavra-chave ou frase a ser pesquisada. |
| `source` | `string` | Não | `"all"` | Filtrar por origem. Valores permitidos: `"all"`, `"wordpress"`, `"nextjs"`. |

### Esquema de Resposta (Array de Objetos)
```json
[
  {
    "id": "1234 (ID WP) ou caminho-github",
    "title": "Título do Artigo ou Seção",
    "excerpt": "Resumo curto ou trecho do texto...",
    "date": "2023-10-25T10:00:00Z",
    "link": "https://ambiental.media/url-completa",
    "source": "wordpress \| nextjs:mata-nativa"
  }
]
```
*Nota: Se nenhum resultado for encontrado, a ferramenta lança um `ToolError` com uma dica semântica para o LLM tentar palavras-chave diferentes.*

---

## 2. `get_full_article`

**Objetivo:** Recupera o texto completo e limpo de um artigo ou projeto específico do WordPress. Remove tags HTML, shortcodes e artefatos de layout.

### Parâmetros de Solicitação
| Nome | Tipo | Obrigatório | Padrão | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `url_or_id` | `string` | **Sim** | - | O ID numérico do WordPress ou a URL completa do artigo. |

### Esquema de Resposta (Objeto)
```json
{
  "title": "Título Completo do Artigo",
  "date": "2023-10-25T10:00:00Z",
  "link": "https://ambiental.media/url-completa",
  "content": "O corpo do artigo totalmente limpo e em texto simples, pronto para sumarização ou análise pelo LLM..."
}
```

---

## 3. `list_latest_news`

**Objetivo:** Retorna as publicações mais recentes. Útil para fornecer contexto temporal ao agente sobre o que está acontecendo atualmente.

### Parâmetros de Solicitação
| Nome | Tipo | Obrigatório | Padrão | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `integer`| Não | `5` | Número de artigos recentes a retornar (Máx: 20). |

### Esquema de Resposta (Array de Objetos)
*(Segue exatamente o mesmo esquema de `search_content` sem o campo `source`, pois consulta apenas a publicação principal do WordPress).*
```json
[
  {
    "id": "1234",
    "title": "Título do Artigo Recente",
    "excerpt": "Resumo curto...",
    "date": "2023-10-25T10:00:00Z",
    "link": "https://ambiental.media/url-completa"
  }
]
```

## 4. Endpoints do Proxy OAuth 2.1 (API Interna)

Estes endpoints são usados internamente para facilitar o fluxo Native MCP OAuth 2.1 entre o Claude Desktop, o portal Next.js `jor-mcp-site` e o backend `jor-mcp`.

### Semântica de Erro Consistente
Todos os endpoints OAuth seguem este esquema de erro padrão para respostas não-2xx:
```json
{
  "error": "invalid_request",
  "error_description": "Detalhes legíveis por humanos (ex: falha na verificação PKCE)"
}
```

### Política de CORS
Todas as rotas `/api/oauth/*` são servidas atrás de um middleware de CORS para que
o portal de consentimento no navegador (`jor-mcp-site`) possa chamá-las via AJAX.
Elas também ignoram a autenticação Firebase e o rate limiting — são o mecanismo
pelo qual os clientes obtêm os tokens Firebase em primeiro lugar.

*   **Origens Permitidas:** configuradas pela variável de ambiente
    `CORS_ALLOWED_ORIGINS` (separadas por vírgula). Padrão: `http://localhost:3000`
    (portal de dev) e `https://jor-mcp.ambiental.media` (portal de prod).
*   **Métodos Permitidos:** `GET`, `POST`, `OPTIONS`.
*   **Cabeçalhos Permitidos:** `Authorization`, `Content-Type`.

---

### 4.0 Saúde do Roteador
**Endpoint:** `GET /api/oauth/health`
**Objetivo:** Sonda de liveness do roteador do proxy OAuth. Não requer autenticação.

**Esquema de Resposta (200 OK):**
```json
{
  "status": "ok",
  "service": "jor-mcp-oauth"
}
```

---

### 4.1 Registro Dinâmico de Cliente (DCR)
**Endpoint:** `POST /api/oauth/register`
**Objetivo:** Chamado pelo Claude Desktop para registrar-se e obter um `client_id`.

**Esquema de Solicitação:**
```json
{
  "client_name": "string",
  "redirect_uris": ["string"],
  "token_endpoint_auth_method": "none"
}
```

**Esquema de Resposta (201 Created):**
```json
{
  "client_id": "uuid-string",
  "client_name": "string",
  "redirect_uris": ["string"],
  "token_endpoint_auth_method": "none"
}
```

---

### 4.2 Aprovação de Consentimento
**Endpoint:** `POST /api/oauth/approve`
**Objetivo:** Chamado pelo `jor-mcp-site` (Next.js) após o usuário clicar em "Permitir". Requer CORS.

**Esquema de Solicitação:**
*(Requer `Authorization: Bearer <Firebase_ID_Token>` para provar a identidade do usuário)*
```json
{
  "client_id": "uuid-string",
  "code_challenge": "string",
  "redirect_uri": "string"
}
```

**Esquema de Resposta (200 OK):**
```json
{
  "authorization_code": "short-lived-random-string",
  "redirect_uri": "http://127.0.0.1:54321/callback?code=..."
}
```

---

### 4.3 Troca de Token
**Endpoint:** `POST /api/oauth/token`
**Objetivo:** Chamado pelo Claude para trocar o `authorization_code` por tokens de Acesso/Refresh do Firebase. Usa `application/x-www-form-urlencoded`.

**Parâmetros de Solicitação:**
*   `grant_type`: `"authorization_code"`
*   `client_id`: `"uuid-string"`
*   `code`: `"short-lived-random-string"`
*   `code_verifier`: `"string"` (validador PKCE)
*   `redirect_uri`: `"string"`

**Esquema de Resposta (200 OK):**
```json
{
  "access_token": "firebase-jwt-string",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "firebase-long-lived-string"
}
```
