<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Firebase and Firestore Integration

*(Placeholder: Details on OAuth 2.1 implementation, Firebase Auth JWT validation, and Firestore atomic transactions for rate limiting).*

## Architectural Decision: Why Serverless State?
We rely on Firestore rather than an in-memory cache or a provisioned Redis instance to maintain statelessness in the Cloud Run containers. This allows horizontal scaling to zero, maximizing FinOps efficiency while preventing rate-limit circumvention during traffic spikes.