# Firebase and Firestore Integration

*(Placeholder: Details on OAuth 2.1 implementation, Firebase Auth JWT validation, and Firestore atomic transactions for rate limiting).*

## Architectural Decision: Why Serverless State?
We rely on Firestore rather than an in-memory cache or a provisioned Redis instance to maintain statelessness in the Cloud Run containers. This allows horizontal scaling to zero, maximizing FinOps efficiency while preventing rate-limit circumvention during traffic spikes.