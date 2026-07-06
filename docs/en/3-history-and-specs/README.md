<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Project Journey

The `jor-mcp` project was born from a vision to provide investigative journalism organizations with a secure, modular, and replicable infrastructure for structured journalistic data. 

## Funding & Support
This project was made possible through the generous support of two major global journalism initiatives:

*   **[JournalismAI Innovation Challenge](https://www.journalismai.info/programmes/innovation):** Supported via "JournalismAI" (a project of POLIS Journalism at LSE) and the "Google News Initiative," targeting the global journalism ecosystem.
*   **[Codesinfo](https://codesinfo.com.br/en/home-english/):** Supported via "Projor" and the "Google News Initiative," targeting the Brazilian journalism ecosystem.

## Project Mission
Our core mission is to lower technical barriers for newsrooms by providing open-source code, adoption guides, and a public landing page to facilitate the integration of AI with editorial content, ensuring newsrooms can securely and ethically search, retrieve, and analyze their proprietary data.

## Project Evolution

### Phase 1: Foundation and Governance (Early 2026)
The project began by focusing on consolidation of strategic planning and technical investigation. We established rigorous workflows using ClickUp, tracking over 80+ actionable tickets, and began a series of technical "spikes" to map MCP resources, define telemetry strategies (OpenTelemetry), and establish open-source best practices. A critical outcome was the definition of our governance and legal requirements, ensuring alignment with data protection regulations and intellectual property protection for journalistic content.

### Phase 2: Mentorship and Architectural Pivot (Spring 2026)
The project underwent a significant architectural evolution following mentorship from Abdullah Enes Gules (Context7/Upstash). This phase marked the pivot to the definitive v1 architecture:
*   **Statelessness:** Adopting a fully stateless FastMCP application on Google Cloud Run.
*   **OAuth 2.1 (PKCE):** Pivoting from static API keys to a standard-compliant, interactive OAuth flow for seamless Claude Desktop connectivity.
*   **Low Tool Count:** Adopting a philosophy of coarse-grained tools to optimize LLM context and performance.
*   **Observability:** Integrated OpenTelemetry auto-instrumentation from the outset for production-grade tracing.

### Phase 3: Launch Readiness & Sustainability (Late Spring 2026)
In this stage, the project transitioned from pure R&D to launch readiness. We finalized the branding and visual identity—designed to represent data flow and processing—and built the `jor-mcp-site` portal to bridge the gap between technical infrastructure and user consent. We also established B2B onboarding workflows, enabling newsrooms to negotiate paid plans directly, followed by manual admin-led tier provisioning (Basic/Pro) in Firestore.

## Contents
- [Project Timeline](project-timeline.md)
- [Specs](specs/)
- [ADRs](adrs/)
- [Reports](reports/)
- [Roadmap](roadmap.md)
- [Visual Identity](visual-identity.md)
