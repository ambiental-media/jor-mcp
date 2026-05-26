# API & Tool Contracts

This document defines the strict interfaces for the tools exposed by the Jor-MCP server. These are the operations the LLM Client can invoke.

*Note: While this documentation is in English, the `description` fields injected into the `@mcp.tool()` decorators in the Python codebase must be written in Portuguese to provide localized context to the LLMs.*

---

## 1. `search_content`

**Purpose:** Unified full-text search across all Ambiental Media properties (WordPress sites and Next.js microsites).

### Request Parameters
| Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | **Yes** | - | The keyword or phrase to search for. |
| `source` | `string` | No | `"all"` | Filter by source. Allowed values: `"all"`, `"wordpress"`, `"nextjs"`. |

### Response Schema (Array of Objects)
```json
[
  {
    "id": "1234 (WP ID) or github-path",
    "title": "Article or Section Title",
    "excerpt": "Short summary or text snippet...",
    "date": "2023-10-25T10:00:00Z",
    "link": "https://ambiental.media/full-url",
    "source": "wordpress | nextjs:mata-nativa"
  }
]
```
*Note: If no results are found, the tool throws a `ToolError` with a semantic hint for the LLM to try different keywords.*

---

## 2. `get_full_article`

**Purpose:** Retrieves the complete, cleaned text of a specific WordPress article or project. It strips HTML tags, shortcodes, and layout artifacts.

### Request Parameters
| Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `url_or_id` | `string` | **Yes** | - | The numeric WordPress ID or the full URL of the article. |

### Response Schema (Object)
```json
{
  "title": "Full Article Title",
  "date": "2023-10-25T10:00:00Z",
  "link": "https://ambiental.media/full-url",
  "content": "The fully cleaned, plain-text body of the article ready for LLM summarization or analysis..."
}
```

---

## 3. `list_latest_news`

**Purpose:** Returns the most recent publications. Useful for providing the agent with temporal context about what is currently happening.

### Request Parameters
| Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `integer`| No | `5` | Number of recent articles to return (Max: 20). |

### Response Schema (Array of Objects)
*(Follows the exact same schema as `search_content` without the `source` field, as it only queries the main WordPress publication).*
```json
[
  {
    "id": "1234",
    "title": "Recent Article Title",
    "excerpt": "Short summary...",
    "date": "2023-10-25T10:00:00Z",
    "link": "https://ambiental.media/full-url"
  }
]
```
