<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# SPEC-001: Jor-MCP v1 Core Architecture & Implementation

## 1. Meta
- **Title:** Jor-MCP v1 Core Architecture & Implementation
- **Status:** Approved
- **Authors:** Ambiental Media Engineering Team
- **Date:** April 2026

## 2. Context & Goals

### 2.1 Background
Following a successful Proof of Concept (POC) deployed on Google Cloud Run and technical mentorship from the Context7/Upstash team, the Jor-MCP project is transitioning to its definitive v1 architecture. The POC validated the feasibility of using the Model Context Protocol (MCP) to distribute journalistic content from WordPress and Next.js (GitHub) to AI agents via Server-Sent Events (SSE) over HTTP. The mentorship highlighted the need for a stateless architecture, OAuth-based authentication, explicit system prompts, and a "low tool count" philosophy to optimize LLM context windows.

### 2.2 Goals
- **Stateless Architecture:** Ensure the MCP server remains entirely stateless, enabling seamless horizontal scaling on Google Cloud Run.
- **Robust Security:** Implement OAuth 2.0 authentication using Firebase Auth / Google Identity Platform and distributed rate limiting via Google Cloud Firestore.
- **Real-time Unified Search:** Fetch and aggregate content synchronously from WordPress REST APIs and GitHub APIs (Next.js JSON files) without relying on intermediate databases.
- **LLM Context Optimization:** Emulate a "Low Tool Count" strategy by providing coarse-grained, highly abstracted tools, complemented by explicit server-side instructions (System Prompts).
- **Production Readiness:** Achieve >90% test coverage (`pytest-asyncio`), strict static typing (`mypy`), linting (`ruff`), and comprehensive OpenTelemetry instrumentation.

### 2.3 Non-Goals
- **Vector Database/Semantic Search Integration:** At this stage, we will bypass intermediate indexing or vector databases to prioritize real-time data freshness and architectural simplicity.
- **Complex Write Operations:** The server will remain strictly read-only, exposing investigative journalism content without providing content creation or modification tools to the LLMs.
- **Custom Identity Provider:** We will leverage Firebase Auth instead of building a custom JWT issuer.

## 3. Architecture Design

The system relies on a stateless FastMCP ASGI application hosted on Google Cloud Run, backed by Google Cloud Firestore for distributed rate-limiting.

### 3.1 Components
- **Entrypoint:** Global External Application Load Balancer. Provides a secure public endpoint, handles SSL termination, and fully supports Server-Sent Events (SSE) streaming required by the MCP protocol.
- **Application Server:** Python 3.12+ using `fastmcp` and `uvicorn`, hosted on Cloud Run with ingress restricted to "Internal and Cloud Load Balancing traffic only."
- **Authentication Middleware:** Validates OAuth 2.0 JWTs issued by Firebase Auth using the `firebase-admin` SDK. Extracts custom claims (e.g., `tier`) for authorization rules.
- **Rate Limit Middleware:** A Firestore-backed fixed window counter (using atomic Increment) to enforce monthly quotas. It applies different monthly request limits based on the user's tier (Basic vs. Pro), resetting automatically at the end of the billing cycle.
- **HTTP Client:** A shared, global `httpx.AsyncClient` singleton configured with connection pooling and timeouts to interact with external APIs.
- **Telemetry:** OpenTelemetry auto-instrumentation for FastAPI/ASGI, HTTPX, and Firestore, exporting structured JSON logs compatible with Google Cloud Logging/Trace.

### 3.2 System Flow
1. An LLM Client sends an HTTP request (SSE) containing a `Bearer <Token>` to the Global Load Balancer.
2. The Load Balancer routes the traffic via a Serverless NEG to the internal-only Cloud Run service.
3. The `AuthMiddleware` intercepts the request and validates the signature using Firebase public keys.
4. The `RateLimitMiddleware` checks Firestore against the user's quota tier.
5. The FastMCP server processes the tool invocation.
6. For external data, the server concurrently queries the WordPress REST API and/or the GitHub API.
7. The data is aggregated, cleaned (e.g., HTML parsing for WP), and returned to the LLM.

## 4. API & Interfaces

### 4.1 Server Instructions (System Prompts)
The FastMCP server will be initialized with explicit instructions to guide the LLM's behavior:
*   *Role:* You are an investigative journalism assistant for Ambiental Media.
*   *Constraint:* Rely strictly on the information returned by the provided tools. Do not hallucinate or invent news.
*   *Format:* Present findings objectively, citing the source (WordPress or Next.js microsite).

### 4.2 MCP Tools
To minimize the tool count and cognitive load on the LLM, we will expose only three robust tools:

1.  **`search_content(query: str, source: str = "all")`**
    *   *Description:* Unified search across all Ambiental Media properties (main WordPress site, WordPress microsites, and Next.js GitHub repositories).
    *   *Behavior:* Concurrently queries WP REST API (`?search=query`) and GitHub REST API (parsing `messages/pt.json` and `messages/en.json`).
2.  **`get_full_article(url_or_id: str)`**
    *   *Description:* Retrieves the complete, cleaned text of a specific WordPress article or project.
    *   *Behavior:* Fetches HTML from WP REST API and applies an advanced HTML parser to remove shortcodes, non-textual blocks, and layout artifacts.
3.  **`list_latest_news(limit: int = 5)`**
    *   *Description:* Returns the most recent publications to provide temporal context.
    *   *Behavior:* Queries the main WP site for recent posts.

## 5. Execution Plan

The development is divided into four milestones. Each milestone must pass the `make check` suite before being considered complete.

### Milestone 1: Core Foundation & Security
- [ ] Initialize project dependencies via `uv` (`fastmcp`, `uvicorn`, `google-cloud-firestore`, `firebase-admin`, `httpx`, `opentelemetry`).
- [ ] Implement `AuthMiddleware` leveraging `firebase-admin` for JWT validation.
- [ ] Implement `RateLimitMiddleware` utilizing `google-cloud-firestore`, supporting tiered quotas based on Firebase custom claims.

### Milestone 2: Real-time Data Ingestion
- [ ] Implement `httpx.AsyncClient` singleton with connection pooling and retry logic.
- [ ] Develop the WordPress data fetcher and advanced HTML text cleaner for `get_full_article`.
- [ ] Develop the GitHub API fetcher to decode and parse base64 Next.js JSON files.
- [ ] Implement the `search_content` tool using `asyncio.gather` for concurrent, unified search.

### Milestone 3: LLM Optimization & Low Tool Count
- [ ] Finalize the implementation of the 3 core tools in `src/tools.py`.
- [ ] Write highly detailed, Portuguese-language tool descriptions in the `@mcp.tool()` decorators.
- [ ] Inject the overarching system prompts into the FastMCP initialization.

### Milestone 4: Quality Assurance & CI/CD
- [ ] Instrument the application with OpenTelemetry (ASGI, HTTPX, Firestore).
- [ ] Write exhaustive tests (`pytest-asyncio`) mocking Firestore, Firebase, and external APIs to achieve >90% coverage.
- [ ] Ensure full compliance with `ruff` formatting/linting and `mypy` strict typing.
- [ ] Finalize the multi-stage `Dockerfile` and update deployment documentation for Cloud Run.
