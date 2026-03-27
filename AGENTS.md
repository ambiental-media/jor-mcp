# AI Agent Instructions for jor-mcp

Welcome, AI Agent. This `AGENTS.md` file defines the standard operating procedures, commands, and code style guidelines for the `jor-mcp` project. You must strictly adhere to these instructions to ensure high-quality, safe, and consistent contributions to this repository.

## Project Context
- **Name:** jor-mcp
- **Purpose:** A Model Context Protocol (MCP) server for Ambiental Media, searching journalism content across WordPress and GitHub.
- **Language:** Python >= 3.12
- **Core Libraries:** `fastmcp`, `uvicorn`, `httpx` (async), `pyjwt`, `opentelemetry`
- **Dependency Manager:** `uv`

---

## Prerequisite: Development Standards
Before making any changes, you **must read and adhere to the rules defined in `CONTRIBUTING.md`**. This includes:
- **Language Constraint: All technical communication (commit messages, PR descriptions, code comments, variable names, and documentation) MUST be in English.** (The only exception is the `@mcp.tool()` description parameter, which must remain in Portuguese).
- Using `uv` for all dependency management and task execution.
- Enforcing strict typing, linting (`ruff`), and formatting.
- Ensuring all new code maintains the **90% test coverage minimum**.
- **Validation:** After writing or modifying code, use the `make check` command to run all linters, formatters, type checkers, and tests at once. Do not propose a Pull Request or consider a task finished until `make check` passes completely.
- **Documentation Sync:** For every proposed change, you MUST review and update the `docs/` directory to ensure it accurately reflects the new code, new environment variables, or new architecture. Never submit code changes without checking if the technical, deployment, or usage documentation needs updating.

---

## Code Style & Conventions

### 1. File Structure and Imports
- **Root directory:** All core application source code lives in the `src/` directory.
- **Absolute Imports:** Always use absolute imports anchored at `src`. Do not use relative imports (like `from .config import ...`).
  - *Good:* `from src.config import GITHUB_TOKEN`
  - *Bad:* `from .config import GITHUB_TOKEN`
- **Import Ordering:** Imports must be grouped and sorted. Run `uv run ruff check . --fix` to organize them automatically after writing code.

### 2. Typing
- **Strict Typing:** All function signatures must be fully type-hinted (both parameters and return values).
- **Modern Types:** Use Python 3.12+ native type syntaxes. Do not import `List`, `Dict`, or `Optional` from `typing`.
  - *Good:* `list[dict[str, Any]]`, `str | None`
  - *Bad:* `List[Dict[str, Any]]`, `Optional[str]`
- **Global Variables:** Avoid globals. If necessary (e.g., shared HTTP clients), annotate them appropriately (`_http_client: httpx.AsyncClient | None = None`).

### 3. Asynchronous Programming
- Use `async` and `await` for all I/O bound operations (HTTP requests, file reads/writes).
- **HTTP Clients:** Use `httpx.AsyncClient`. Do not use the synchronous `requests` library.
- **Concurrency:** Use `asyncio.gather(*tasks)` to run multiple independent network requests in parallel. See `search_ambiental` in `src/tools.py` for a reference implementation.
- **Connection Pooling:** Reuse HTTP clients globally across requests to prevent socket exhaustion. Use the singleton pattern established in `_get_client()`.

### 4. Naming Conventions
- **Files/Modules:** `snake_case.py`
- **Classes:** `PascalCase` (e.g., `MCPMiddleware`)
- **Functions/Methods/Variables:** `snake_case` (e.g., `get_full_article`, `client_ip`)
- **Constants:** `UPPER_SNAKE_CASE`. Constants must be strictly defined in `src/config.py` and populated via `os.environ.get`.
- **Internal/Private:** Prefix internal helper functions and variables with an underscore (e.g., `_strip_html`, `_search_wp`, `_requests`).

### 5. Error Handling
- **Specific Exceptions:** Catch narrow, specific exceptions like `httpx.HTTPStatusError` instead of broad `Exception` when possible.
- **MCP Errors:** When a tool fails in a way the LLM needs to know about, raise `fastmcp.exceptions.ToolError` with a clear, descriptive message in Portuguese.
  ```python
  from fastmcp.exceptions import ToolError
  raise ToolError("Erro de conexão ao acessar o WordPress.")
  ```
- **Graceful Degradation:** When aggregating results from multiple sources (e.g., GitHub and WordPress), if one fails, capture the error, append it as a result dictionary (`{"error": "..."}`), and allow the other source to return successfully. Do not crash the entire function or return empty lists if partial data is available.
- **Logging:** Use the standard Python `logging` module. Use `logger.warning` or `logger.error` in middleware or server code. Do not use `print()` in production code.

### 6. Tools and Descriptions
- **Tool Decorators:** Use `@mcp.tool()` to expose functions to the Model Context Protocol.
- **Descriptions:** Every tool must have a highly detailed `description` parameter string in its decorator. Explain exactly what it does, the parameters it accepts, and when an LLM should use it. Write these descriptions in Portuguese, as the target audience/domain is Brazilian journalism.

### 7. Security and Credentials
- **No Hardcoded Secrets:** Never hardcode API keys, passwords, or tokens. Retrieve them via `src/config.py` which delegates to environment variables.
- **Headers:** Ensure Authorization headers are passed correctly when interacting with authenticated APIs (e.g., `"Authorization": f"Bearer {GITHUB_TOKEN}"`).

### 8. External Integrations Performance
- When dealing with external APIs, request only the fields you need. For example, with WordPress, use `_fields=id,title,excerpt,date,link` to limit the payload size.
- Utilize pagination limits and handle rate limiting carefully.
