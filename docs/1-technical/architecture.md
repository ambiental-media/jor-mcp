# Jor-MCP Architecture

This document provides a high-level overview of the Jor-MCP system architecture, detailing how components interact with external systems and illustrating the lifecycle of an incoming request.

## 1. System Context Diagram (C4 Level 1)

This diagram illustrates the Jor-MCP server in its environment. It acts as an orchestrator, receiving requests from an AI Agent (Client), validating authentication via Firebase, applying rate limits via Redis, and fetching data from WordPress and GitHub.

```mermaid
%%{init: {'theme': 'dark'}}%%
graph TD
    %% External Actors
    Client[AI Agent / LLM Client]
    
    %% Core System
    subgraph GCP Environment
        LB[Global Application Load Balancer]
        JorMCP[Jor-MCP Server \n FastMCP / Cloud Run \n Internal Ingress Only]
        Redis[(GCP Memorystore \n Redis)]
    end
    
    %% External Services
    FirebaseAuth[Firebase Auth \n Identity Provider]
    WP[WordPress REST API \n ambiental.media]
    GH[GitHub API \n Next.js JSONs]

    %% Relationships
    Client -- "1. HTTP SSE + Bearer Token" --> LB
    LB -- "2. Route to Serverless NEG" --> JorMCP
    JorMCP -. "3. Validate JWKS" .-> FirebaseAuth
    JorMCP -- "4. Check/Update Quota" --> Redis
    JorMCP -- "5. Fetch Posts/Pages" --> WP
    JorMCP -- "6. Fetch JSON Content" --> GH
    
    %% Styling
    classDef external fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef internal fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef db fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;
    classDef gateway fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    
    class Client,FirebaseAuth,WP,GH external;
    class JorMCP internal;
    class LB gateway;
    class Redis db;
```

## 2. Request Lifecycle (Sequence Diagram)

This sequence diagram details the strict order of operations for every incoming request. It highlights the security layers (Auth and Rate Limiting) executing before the business logic (FastMCP Tools).

```mermaid
%%{init: {'theme': 'dark'}}%%
sequenceDiagram
    participant C as LLM Client
    participant Auth as Auth Middleware
    participant RL as Rate Limit Middleware
    participant Redis as GCP Memorystore
    participant MCP as FastMCP Engine
    participant Ext as External APIs (WP/GH)

    C->>Auth: HTTP POST /mcp (Bearer Token)
    
    Note over Auth: Firebase JWT Validation
    alt Token Invalid/Expired
        Auth-->>C: 401 Unauthorized
    else Token Valid
        Auth->>RL: Forward Request (User ID, Tier)
    end

    Note over RL: Sliding Window Check
    RL->>Redis: GET / SET user requests
    Redis-->>RL: Current Count
    
    alt Quota Exceeded
        RL-->>C: 429 Too Many Requests
    else Quota Available
        RL->>MCP: Execute Tool
    end

    Note over MCP: Tool Logic Execution
    MCP->>Ext: Async HTTP Request (httpx)
    Ext-->>MCP: Raw JSON/HTML Response
    
    Note over MCP: HTML Parsing & Aggregation
    MCP-->>C: Formatted Tool Result (JSON)
```

## 3. Core Technologies

- **Framework:** `fastmcp` (ASGI server powered by `uvicorn`).
- **HTTP Client:** `httpx` (Asynchronous connection pooling).
- **Security:** `firebase-admin` (JWT validation) and `redis.asyncio` (Rate limiting).
- **Telemetry:** OpenTelemetry (`opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`).
