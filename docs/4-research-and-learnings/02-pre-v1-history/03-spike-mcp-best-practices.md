# Pre-POC Spike: MCP Best Practices and Telemetry

## 1. Objective
To establish best practices for building an MCP server, focusing on observability (telemetry), error handling, and LLM context window optimization.

## 2. Telemetry Strategy (OpenTelemetry)

A robust monitoring infrastructure is critical to ensure the health and performance of the MCP server.

*   **Approach:** We will utilize **OpenTelemetry (OTel)**.
*   **Instrumentation:** To minimize code changes, we will rely on **Automatic Instrumentation** (e.g., `opentelemetry-instrumentation-fastapi`, `httpx`, `redis`). Manual instrumentation will be used only for highly specific domain metrics (e.g., tracking token usage if necessary).
*   **Exporting:** To simplify deployment on Cloud Run and avoid managing a sidecar container (OTel Collector), we will use direct **SDK Exporters** (`opentelemetry-exporter-gcp-monitoring` and `opentelemetry-exporter-gcp-trace`).
*   **Key Metrics:**
    *   *Latency:* Tracked via Histograms (p50, p95, p99).
    *   *Availability/Errors:* Tracked via HTTP status codes (2xx vs 5xx) and exception types.

## 3. Error Handling Patterns

Standard HTTP error codes are insufficient for AI agents, as the agent needs semantic understanding of *why* an operation failed to adjust its behavior.

*   **Practice:** When an internal tool fails (e.g., a WordPress article is not found, or a GitHub repo is inaccessible), the server must raise a `ToolError` (specific to the FastMCP framework).
*   **Semantic Hints:** The error message must contain clear, human-readable instructions in Portuguese guiding the LLM on how to recover. For example: *"Artigo não encontrado com este ID. Tente utilizar a ferramenta search_ambiental para buscar por palavras-chave."*

## 4. Context Management (Token Sustainability)

LLMs have limited context windows and charge per token. The MCP server must be responsible for minimizing the payload it returns.

*   **Practice - Server-Side Filtering:** The server must do the heavy lifting. Instead of returning raw HTML from WordPress, the server must implement an HTML parser to strip tags, shortcodes, and navigation elements, returning only the essential article text.
*   **Practice - Pagination and Limits:** Tools like `list_latest_news` must enforce strict upper limits (e.g., max 20 results) to prevent accidentally flooding the LLM context.
*   **Practice - Low Tool Count:** Avoid exposing granular database operations (CRUD). Expose high-level, composite tools (like a unified search) to reduce the cognitive load and token overhead of the agent deciding which tool to use.