<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# WordPress Integration

*(Placeholder: How the WordPress tool fetches, parses, and cleans data. Rate limiting and pagination strategies).*

## Architectural Decision: Why REST API?
We utilize the WordPress REST API rather than GraphQL or direct database connections to ensure compatibility with standard newsroom deployments. The data is heavily cleaned (stripping HTML and shortcodes) on the server side because sending raw HTML to an LLM wastes context window tokens and degrades the model's summarization quality.