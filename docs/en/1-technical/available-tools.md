<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Available Tools Reference

This document provides a detailed reference of the Model Context Protocol (MCP) tools exposed by the Jor-MCP server. These tools allow LLM clients to query and retrieve editorial and journalism content from Ambiental Media's WordPress site and GitHub data repositories.

---

## 1. Unified Search (`search_content`)

This is the **primary tool** and mandatory entry point for any general research or user query regarding published content.

### Description
Performs a concurrent, unified search across both WordPress REST API and multilingual editorial JSON files hosted on GitHub.
- **Accents & Case Insensitivity:** The search normalization strips accents and ignores casing (e.g., searching for "amazonia" matches "Amazônia").
- **Graceful Failure:** If one of the sources is down or fails, it aggregates results from the available source and inserts an error indicator in the result payload rather than failing the whole request.

### Parameters
| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `query` | `string` | The keyword, theme, place, name, or phrase to search for. | **Yes** |

### Return Value (`list[dict[str, Any]]`)
Returns a JSON array of matched items. Each item matches the following schema:
- `id` (`string`): Unique identifier of the resource (e.g., a post ID for WordPress, or `repo/path` for GitHub files).
- `title` (`string`): The clean, HTML-stripped title of the post or file name.
- `excerpt` (`string`): A contextual text snippet containing the matched query window.
- `date` (`string`): Date of publication (`YYYY-MM-DD`) or empty if from GitHub.
- `link` (`string`): Canonical URL to access the full content.
- `source` (`string`): Origin of the match (`"wordpress"` or `"github:<repo>"`).
- `error` (`string`, optional): Present only if one of the backends failed during the query.

---

## 2. List Latest News (`list_latest_news`)

Use this tool when the user asks for general updates, new publications, or overall context without having a specific topic in mind.

### Description
Retrieves a list of the most recently published articles on the WordPress site, sorted in descending chronological order.
- **Abuse Prevention:** The results limit is strictly capped at `20` items to prevent overly large token payloads.

### Parameters
| Name | Type | Default | Description | Required |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `integer` | `5` | Number of recent articles to retrieve (clamped between `1` and `20`). | No |

### Return Value (`list[dict[str, Any]]`)
Returns an array of matched article summaries:
- `id` (`string`): Numeric post ID on WordPress.
- `title` (`string`): The clean title.
- `excerpt` (`string`): Summary/Excerpt text.
- `date` (`string`): Publication date (`YYYY-MM-DD`).
- `link` (`string`): Canonical article URL.
- `source` (`string`): Always `"wordpress"`.

---

## 3. Retrieve Full Article (`get_full_article`)

Use this tool **only** after obtaining a valid URL, ID, or slug from a previous search or news list. Do not try to guess IDs.

### Description
Fetches a specific post from the WordPress REST API and extracts the full body content, removing all HTML markup to return a clean plain-text editorial piece optimized for LLM reading, summarization, and citation.

### Parameters
| Name | Type | Description | Required |
| :--- | :--- | :--- | :--- |
| `url_or_id` | `string` | A numeric post ID (e.g., `"123"`), a full canonical URL (e.g., `"https://ambiental.media/amazon-deforestation/"`), or a bare slug. | **Yes** |

### Return Value (`dict[str, Any]`)
Returns a single object with the clean, full-text content:
- `title` (`string`): Clean title.
- `date` (`string`): Date published (`YYYY-MM-DD`).
- `link` (`string`): Canonical URL (for citation).
- `content` (`string`): Full cleaned article text without HTML tags.
