# Pre-POC Spike: Data Sources and Tools

## 1. Objective
To analyze the "tools" required for the Jor-MCP server to integrate various content sources and formats from Ambiental Media.

## 2. Context
Ambiental Media publishes investigative journalism on environmental, science, and data topics. Content is distributed across multiple platforms: a main WordPress site, several WordPress-based microsites, and Next.js microsites hosted on custom subdomains. The Jor-MCP server acts as an orchestrator, providing high-level tools for an LLM to access this content uniformly. The primary function is read-only.

## 3. Identified Data Sources
| Data Source | URL | Technology |
| :--- | :--- | :--- |
| Main Site | ambiental.media | WordPress |
| Aquazonia | aquazonia.ambiental.media | Next.js |
| Rio 60 | rio60.ambiental.media | Next.js |
| Cerrado | cerrado.ambiental.media | Next.js |
| Cortina de Fumaça | cortinadefumaca.ambiental.media | WordPress |
| Hiperdiversidade | hiperdiversidade.ambiental.media | WordPress |
| Floresta Silenciosa | florestasilenciosa.ambiental.media | WordPress |

### 3.1 Next.js Microsites
These are Next.js 13+ applications following a standardized template, hosted in private GitHub repositories under the `ambiental-media` organization.

*   **Content Location:** Text is centralized in JSON files (`messages/pt.json` and `messages/en.json`). React components reference these via `useTranslations()`.
*   **Assets:** Hosted in the `public/` folder.

### 3.2 WordPress Sites
Four active WordPress sites were confirmed, all utilizing a MariaDB database and exposing a functional REST API.

*   **Main Site (ambiental.media):** Uses standard Posts, a Custom Post Type for "Projects," and Pages. Built heavily with Elementor.
*   **Microsites:** Structurally simpler, relying primarily on static Pages and presentation plugins (Portfolios, Galleries). They do not actively use standard Posts or Custom Post Types.

**REST API Testing:** The `/wp-json/wp/v2/` endpoints for posts, projects, categories, and pages were successfully tested, supporting search queries and pagination.

## 4. Integration Strategy

The Jor-MCP orchestrator will delegate access based on the source technology.

### 4.1 Next.js Integration (GitHub)
Two options were evaluated for accessing the private GitHub repositories:
1.  **Via GitHub MCP Server:** Reuses existing infrastructure but introduces an external dependency, higher latency, and complex deployment.
2.  **Via Direct GitHub REST API:** Direct HTTP requests to fetch JSON files. Offers total control, lower latency, simpler deployment, and avoids inter-process communication overhead.
*   **Decision:** Proceed with the **Direct GitHub REST API** for the MVP due to its simplicity and lower latency. Authentication will use a Personal Access Token (PAT).

### 4.2 WordPress Integration
*   **Decision:** Utilize the **WordPress REST API**. It fully meets the MVP needs (text search, custom post types, filtering, pagination) and abstracts database complexities. Direct SQL queries are reserved for future needs if highly complex queries arise.

## 5. Proposed Tools (Abstract Interface)

The tools are defined by their semantic operation, unifying the underlying data sources.

*   **`search_content`**: Unified search across Next.js JSONs and WordPress REST APIs.
*   **`get_full_article`**: Retrieves complete, cleaned text from a WordPress post/page.
*   **`list_latest_news`**: Retrieves recent publications for temporal context.
