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
