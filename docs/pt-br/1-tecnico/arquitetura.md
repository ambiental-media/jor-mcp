# Arquitetura do Jor-MCP

Este documento fornece uma visão geral de alto nível da arquitetura do sistema Jor-MCP, detalhando como os componentes interagem com sistemas externos e ilustrando o ciclo de vida de uma solicitação recebida.

## 1. Diagrama de Contexto do Sistema (C4 Nível 1)

Este diagrama ilustra o sistema Jor-MCP, incluindo a interação entre o cliente Claude Desktop, o Servidor de API em Python (atuando como um Proxy OAuth) e o Portal para consentimento do usuário.

```mermaid
%%{init: {'theme': 'dark'}}%%
graph TD
    %% Atores Externos
    Client[Agente de IA / Cliente LLM]
    
    %% Sistema Principal
    subgraph Ambiente GCP
        LB[Load Balancer Global]
        Portal[Jor-MCP Site \n Portal Next.js]
        JorMCP[Servidor Jor-MCP \n FastMCP / Cloud Run]
        Firestore[(Google Cloud Firestore)]
    end
    
    %% Serviços Externos
    FirebaseAuth[Firebase Auth]
    WP[WordPress REST API]
    GH[GitHub API]

    %% Relacionamentos
    Client -- "1. Fluxo MCP OAuth 2.1" --> LB
    LB -- "2. Rota /mcp/*" --> JorMCP
    LB -- "2. Rota /api/oauth/*" --> JorMCP
    LB -- "2. Rota /*" --> Portal
    
    Portal -- "3. Autentica Usuário" --> FirebaseAuth
    Portal -- "4. Armazena Consentimento/Tier" --> Firestore
    
    JorMCP -- "5. DCR & Troca de Token" --> FirebaseAuth
    JorMCP -- "6. Valida Tier/Quota" --> Firestore
    
    JorMCP -- "7. Busca Conteúdo" --> WP
    JorMCP -- "8. Busca Conteúdo JSON" --> GH
    
    class Client,FirebaseAuth,WP,GH externo;
    class JorMCP,Portal interno;
    class LB gateway;
    class Firestore db;
```

## 2. Ciclo de Vida da Solicitação (Diagrama de Sequência)

Este diagrama detalha o fluxo nativo do MCP OAuth 2.1.

```mermaid
%%{init: {'theme': 'dark'}}%%
sequenceDiagram
    participant C as Cliente LLM
    participant Proxy as Camada Proxy Jor-MCP
    participant Portal as Portal de Consentimento Next.js
    participant Auth as Firebase Auth
    participant MCP as Engine FastMCP
    participant Ext as APIs Externas

    C->>Proxy: 1. Descoberta/DCR
    Proxy-->>C: 2. Metadados de Descoberta Auth
    
    C->>Portal: 3. Popup do Navegador / Consentimento
    Portal->>Auth: Login
    Portal->>Proxy: 4. Código de Auth
    
    C->>Proxy: 5. Troca de Token (PKCE)
    Proxy->>Auth: 6. Emissão de Access/Refresh Tokens
    Proxy-->>C: 7. Tokens

    C->>MCP: 8. Solicitação de Ferramenta MCP (Bearer Token)
    Note over MCP: Valida Token & Tier
    MCP->>Ext: 9. Solicitação de Dados
    Ext-->>MCP: 10. Resposta
    MCP-->>C: 11. Resultado da Ferramenta
```

## 3. Tecnologias Principais

- **Framework:** `fastmcp` (Servidor ASGI impulsionado pelo `uvicorn`).
- **Cliente HTTP:** `httpx` (Pool de conexões assíncronas).
- **Segurança:** `firebase-admin` (validação de JWT) e `google-cloud-firestore` (limitação de taxa).
- **Telemetria:** OpenTelemetry (`opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`).
