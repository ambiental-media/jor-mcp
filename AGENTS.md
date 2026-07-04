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

## Code Style, Conventions & Python Best Practices

AI Agents operating in this repository must strictly adhere to the following community best practices and modern Python 3.12+ paradigms.

### 1. File Structure, Imports & Project Layout
- **PEP 8:** Style Guide for Python Code (The foundational aesthetic standard).
- **PEP 20:** The Zen of Python (Guiding philosophy for clean code).
- **PEP 695:** Type Parameter Syntax (Modern 3.12+ generics and type aliases).
- **The "Src Layout":** All source code must reside in `src/`. This forces tests to run against the installed package rather than the local folder, preventing accidental import leaks.
- **Absolute Imports:** Always use absolute imports anchored at `src`. Do not use relative imports (like `from .config import ...`).
  - *Good:* `from src.config import GITHUB_TOKEN`
  - *Bad:* `from .config import GITHUB_TOKEN`
- **Import Ordering:** Imports must be grouped and sorted. Run `uv run ruff check . --fix` to organize them automatically after writing code.
- **Dependency Management:** Use `uv` as the single source of truth for dependency management.
- **Tooling:** Use `Ruff` for all linting and formatting (rules: E, F, I, UP, S, B), replacing Flake8, Isort, and Black.

### 2. Modern Typing, Idioms & Data Validation (3.12+)
This project strictly utilizes a dual-strategy for type safety:
- **Internal Logic (Static Analysis):** All functions must be fully type-hinted using Python 3.12+ native syntax (`list[dict[str, Any]]`, `str | None`). Avoid importing capital types (`List`, `Dict`) from `typing`. `mypy` enforces these rules statically.
- **System Boundaries (Runtime Validation):** Use **Pydantic (v2)** `BaseModel`s for strict, type-safe data validation at the boundaries of the application. This includes parsing external API responses (e.g., WordPress/GitHub JSON), environment variables, and client request payloads. Never trust external data; always validate it through a Pydantic model before passing it into core internal logic.
- **Modern Built-ins:** Leverage modern Python methods. For instance, use `str.removeprefix("Bearer ")` instead of manual string slicing (`auth_header[len("Bearer "):]`).
- **Protocols:** Use `typing.Protocol` for duck-typing and decoupling components, especially when defining interfaces for external services or mocks.

### 3. Asynchronous Programming
- Use `async` and `await` for all I/O bound operations (HTTP requests, file reads/writes).
- **HTTP Clients:** Use `httpx.AsyncClient`. Do not use the synchronous `requests` library.
- **Concurrency (3.11+):** Prefer `asyncio.TaskGroup` over `asyncio.gather` for managing multiple concurrent tasks. TaskGroups provide vastly superior error handling and predictable task cancellation.
- **Connection Pooling:** Reuse HTTP clients globally across requests to prevent socket exhaustion. Use the singleton pattern established in `_get_client()`.
- **ASGI Lifespans:** Do not initialize heavy external clients (e.g., Firebase, HTTP connection pools) inside the `__init__` of middleware or routers. Always use the ASGI `lifespan` context manager in `src/server.py` to ensure safe startup/teardown across multiple async workers.

### 4. Naming Conventions & Documentation
- **Files/Modules:** `snake_case.py`
- **Classes:** `PascalCase` (e.g., `MCPMiddleware`)
- **Functions/Methods/Variables:** `snake_case` (e.g., `get_full_article`, `client_ip`)
- **Constants:** `UPPER_SNAKE_CASE`. Constants must be strictly defined in `src/config.py` and populated via `os.environ.get`.
- **Internal/Private:** Prefix internal helper functions and variables with an underscore (e.g., `_strip_html`, `_search_wp`, `_requests`).
- **Documentation (Google Style):** All functions, classes, and modules must follow the Google Python Style Guide.
  > **Format Example:**
  > ```python
  > def fetch_data(api_key: str, timeout: int = 10) -> dict[str, Any]:
  >     """Fetches a record from the internal API.
  >
  >     Args:
  >         api_key: The authenticated secret for the API.
  >         timeout: Max seconds to wait for a response. Defaults to 10.
  >
  >     Returns:
  >         A dictionary containing the parsed JSON response.
  >
  >     Raises:
  >         ConnectionError: If the server is unreachable.
  >     """
  > ```

### 5. Error & Exception Handling
Python 3.12 features advanced error messages and tracebacks.
- **Granularity:** Never use a bare `except:`. Always catch specific exceptions (like `httpx.HTTPStatusError`). Avoid catching broad built-in exceptions like `ValueError` or `Exception` around large blocks of code.
- **Exception Groups (3.11+):** Use `except*` when dealing with concurrent tasks (like `TaskGroup`) to handle multiple failures simultaneously.
- **Contextlib:** Use `contextlib.suppress(SpecificException)` for intentional, explicit error ignoring instead of `try...except...pass`.
- **MCP Errors:** When a tool fails in a way the LLM needs to know about, raise `fastmcp.exceptions.ToolError` with a clear, descriptive message in Portuguese.
- **Graceful Degradation:** When aggregating results from multiple sources (e.g., GitHub and WordPress), if one fails, capture the error, append it as a result dictionary (`{"error": "..."}`), and allow the other source to return successfully.

### 6. Logging & Observability (OpenTelemetry Auto-Instrumentation)
This project relies on OpenTelemetry auto-instrumentation. You do not need to manually create traces or spans in the code.
- **Standard Logging:** Always initialize standard loggers via `logger = logging.getLogger(__name__)`. OpenTelemetry automatically intercepts these logs and attaches trace IDs.
- **Structured Data:** Do NOT use string interpolation for data you want to query later (e.g., `logger.info(f"User {uid} logged in")`). Instead, use the `extra` parameter: `logger.info("User logged in", extra={"user_id": uid})`. The auto-instrumentation will extract the `extra` dict into proper OTLP log attributes.
- **Exception Logging:** Use `logger.exception()` inside error handlers to automatically attach full stack traces to the active auto-generated span.
- **Log Noise Reduction:** Use `logger.warning()` for expected client-side rejections (e.g., 401 Unauthorized) to avoid spamming the observability backend with useless stack traces and false "Error" metrics.

### 7. Modern Unit Testing (pytest)
Pytest is the gold standard. The approach emphasizes composition over inheritance.
- **Fixtures:** Use `conftest.py` for shared resources. Avoid the `unittest.TestCase` class structure unless legacy support strictly requires it.
- **Assertions:** Stick to plain `assert` statements; let pytest's introspection handle the diffs.
- **Parametrization:** Liberally use `@pytest.mark.parametrize` to test edge cases and reduce code duplication.
- **Async Testing:** Utilize `pytest-asyncio` for the event loop.
- **Mocking Strategy:** Prefer function-level `@patch` decorators over `with patch():` context managers to keep code indentation flat, unless testing an extremely isolated block. Or use dependency injection via fixtures to avoid heavy mocking entirely.
- **Middleware Testing:** When testing ASGI middleware state injection, use the "Spy App" pattern (passing a dummy async function to capture `scope`) to verify internal state mutations, alongside standard `TestClient` HTTP tests.
- **Coverage:** Minimum 90% coverage required (verified via `pytest-cov`).

### 8. Security Practices
- **Secrets Management:** Never hardcode secrets. Always use `.env` templates, `python-dotenv`, or environment variables injected by the cloud provider.
- **Input Validation:** Use `Pydantic` (v2) for strict, type-safe data validation at the boundaries of the application (e.g., API payloads, config files).
- **Defensive Decoding:** Never blindly decode raw ASGI bytes (e.g., headers or body). Always account for malicious payloads by using `decode("utf-8", errors="ignore")` or catching `UnicodeDecodeError` to prevent HTTP 500 server crashes.
- **Path Traversal:** Always use `pathlib.Path` over `os.path` for file system operations. Resolve paths strictly (`path.resolve(strict=True)`) to mitigate path traversal attacks.
- **Subprocesses:** Never use `os.system` or `subprocess.run(..., shell=True)` with unvalidated input to prevent shell injection vulnerabilities.
- **Headers:** Ensure Authorization headers are passed correctly when interacting with authenticated APIs.
- **Dependencies:** Keep dependencies locked and deterministic via `uv`.

### 9. External Integrations & Tool Descriptions
- **Performance:** When dealing with external APIs, request only the fields you need. For example, with WordPress, use `_fields=id,title,excerpt,date,link` to limit the payload size. Utilize pagination limits and handle rate limiting carefully.
- **Tool Decorators:** Use `@mcp.tool()` to expose functions to the Model Context Protocol.
- **Descriptions:** Every tool must have a highly detailed `description` parameter string in its decorator. Explain exactly what it does, the parameters it accepts, and when an LLM should use it. Write these descriptions in Portuguese, as the target audience/domain is Brazilian journalism.


