<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


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
        GCSBucket[(Google Cloud Storage \n Exportação Estática)]
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
    LB -- "2. Rota /*" --> GCSBucket
    
    GCSBucket -- "3. Autentica Usuário" --> FirebaseAuth
    GCSBucket -- "4. Armazena Consentimento/Tier" --> Firestore
    
    JorMCP -- "5. DCR & Troca de Token" --> FirebaseAuth
    JorMCP -- "6. Valida Tier/Quota" --> Firestore
    
    JorMCP -- "7. Busca Conteúdo" --> WP
    JorMCP -- "8. Busca Conteúdo JSON" --> GH
    
    class Client,FirebaseAuth,WP,GH externo;
    class JorMCP,GCSBucket interno;
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

- **Hospedagem Frontend:** `Google Cloud Storage` e `Cloud CDN` para cache global na borda (edge) dos ativos estáticos do Next.js.
- **Framework:** `fastmcp` (Servidor ASGI impulsionado pelo `uvicorn`).
- **Cliente HTTP:** `httpx` (Pool de conexões assíncronas).
- **Segurança:** `firebase-admin` (validação de JWT) e `google-cloud-firestore` (limitação de taxa).
- **Telemetria:** OpenTelemetry (`opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`).

## 4. Padrões de Arquitetura Chave

### 4.1 Camada de Validação de Dados
Toda entrada de dados externos (respostas de API do WordPress/GitHub, variáveis de ambiente, solicitações de clientes) deve passar por uma camada de validação do **Pydantic v2**. Isso garante que a lógica principal da aplicação, verificada estaticamente pelo Mypy, opere apenas em estruturas garantidas e seguras quanto ao tipo (type-safe).

### 4.2 Telemetria e Observabilidade
A aplicação depende estritamente da **Auto-Instrumentação do OpenTelemetry**. Rastreamentos (traces), métricas e logs são coletados automaticamente a partir da camada ASGI (FastMCP/Starlette), clientes HTTP (`httpx`) e do módulo padrão `logging` do Python.
- **Sem Rastreamento Manual:** Os desenvolvedores devem evitar a importação de componentes do SDK do `opentelemetry` na lógica de negócios.
- **Registro de Logs:** Use o módulo padrão `logging` do Python. Todos os logs são automaticamente interceptados, enriquecidos com contextos de rastreamento e exportados via OTLP para o backend de observabilidade configurado.
