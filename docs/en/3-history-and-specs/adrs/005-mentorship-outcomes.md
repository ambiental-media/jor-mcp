<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Technical Mentorship Outcomes

**Date:** Pre-v1 Planning Phase
**Mentor:** Abdullah Enes Gules (Principal Contributor, Context7 MCP / Upstash)

## 1. Overview
Following the POC, the team engaged in a technical mentorship session to review the architecture and align it with industry best practices for MCP servers. The session yielded several critical architectural pivots that define the v1 specification.

## 2. Key Architectural Decisions

### 2.1 Architecture and Security
*   **Statelessness:** Strongly reaffirmed the need for a stateless server to ensure seamless scalability on Google Cloud Run.
*   **OAuth Integration:** Given that the final LLM client will likely be web-based, the mentorship strongly recommended decoupling authentication from the core logic and migrating to standard **OAuth 2.0**.
*   *Reference material provided:* Upstash Blog on MCP OAuth Implementation.

### 2.2 Performance and Tool Optimization
*   **Low Tool Count Philosophy:** The mentor emphasized exposing a very small, highly abstracted number of tools.
    *   *Rationale:* High granularity confuses the LLM, wastes context window tokens with excessive tool descriptions, and degrades performance.
*   **Server-Side Responsibility:** The server must do the heavy lifting (data aggregation, cleaning, and formatting) before sending data to the LLM. This reduces cognitive load on the model and prevents hallucinations.

### 2.3 System Prompts
*   **Embedded Instructions:** Recommended utilizing the server's initialization capabilities to embed "System Prompts" (`FastMCP(instructions=...)`). These instruct the LLM on exactly how to behave when interacting with the journalism tools, establishing guardrails.
    *   *Reference material provided:* Context7 source code (`src/index.ts`).

### 2.4 Semantic Search (Deferred)
*   **Vector Search Discussion:** The use of Vector Databases (Semantic Search) was discussed to improve search accuracy over basic REST API textual search.
*   *Outcome:* While valuable, the team decided to **defer** Vector DB integration from the v1 architecture to prioritize real-time ingestion (stateless REST calls) and minimize infrastructure complexity in the initial release.

## 3. Impact on v1 Specification
These mentorship outcomes directly informed [SPEC-001-v1-core](../specs/SPEC-001-v1-core.md), leading to the adoption of Firebase Auth (OAuth), Google Cloud Firestore (for stateless rate limiting), the strict 3-tool limit, and the inclusion of explicit server instructions.