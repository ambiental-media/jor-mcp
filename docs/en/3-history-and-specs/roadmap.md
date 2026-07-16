<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Jor-MCP Project Roadmap

This document outlines the high-level goals and upcoming features for the Jor-MCP project. It provides transparency into our current focus areas and what users can expect in the future.

## Currently Under Development 🏗️
*   **Native MCP OAuth 2.1 Integration:** Transitioning from static API keys to a fully interactive OAuth flow using PKCE for zero-configuration Claude Desktop connections.
*   **Next.js Portal Development:** Building the `jor-mcp-site` to handle user consent and authentication via Google SSO.
*   **Security & Infrastructure Hardening:** Audit and patch vulnerabilities in the frontend portal (XSS, Open Redirect), implement IP-based rate limiting on public backend routes, and apply the principle of least privilege (IAM) to the Cloud Run infrastructure.
*   **Legal Framework:** Establish the legal foundation for the project, including defining the Open Source License, drafting Terms of Use for the public instance, and creating the Privacy Policy for user data handling.

## Next Up (Near Term) ⏳
*   **Token-Based Rate Limiting & Weekly Quotas:** Migrate from request-based limits to token-consumption-based limits, moving from monthly to weekly reset cycles for tighter control and more precise billing metrics.
*   **Firebase Authentication Expansion:** Exploring Firebase configuration to enable additional authentication methods such as Google, OpenID Connect (OIDC), SAML, Microsoft, and Apple.
*   **Replication Validation (Pilot Program):** Select and collaborate with an initial pilot partner journalism organization to deploy `jor-mcp` in their infrastructure. We will provide dedicated hands-on support, using the lessons learned to generate a standardized **Replication Playbook**, **Infrastructure as Code (IaC)**, and **Configuration as Code (CaC)** blueprints to make future deployments friction-free. Interested partner organizations are invited to reach out to us to join this first pilot round.
*   **Sustainability Models:** Exploration of sustainability and commercialization models for JOR-MCP, aiming to ensure its continuity and expand its potential impact.
*   **User Testing & Feedback Sessions:** Organize and conduct controlled testing sessions with selected users to collect structured feedback, identify bugs, and uncover feature opportunities. Testing reports will be generated to inform the project's next iteration cycles.

## Future Vision (Long Term) 🚀
(To be defined)

---
*Note: This roadmap is a living document and subject to change based on community feedback and project priorities.*
