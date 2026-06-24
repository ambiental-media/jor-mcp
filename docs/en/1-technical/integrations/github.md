# GitHub Integration

*(Placeholder: How the GitHub tool queries repositories, handles authentication tokens, and limits search scopes).*

## Architectural Decision: Why Parse JSON?
For Next.js microsites hosted on GitHub, we specifically parse the pre-rendered `messages/*.json` files rather than raw Markdown or React `.tsx` files. This ensures the LLM receives structured, final content without hallucinating over UI logic or unrendered variables.