<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Configuração do Load Balancer Global

## 1. Visão Geral
O Global External Application Load Balancer atua como o único ponto de entrada para `jormcp.ambiental.media`. Ele tem duas funções críticas:
1.  **Terminação SSL/TLS:** Gerencia o certificado SSL gerenciado pelo Google.
2.  **Roteamento Baseado em Caminho:** Divide o tráfego entre a API Python (Cloud Run) e o Frontend Next.js (Cloud Storage).

*Nota: Estas instruções pressupõem provisionamento manual através do Google Cloud Console.*

## 2. Configuração de Serviços de Backend
Para rotear o tráfego corretamente, você deve criar dois serviços de backend distintos no GCP.

### 2.1 Serviço de Backend: API (Serverless NEG)
*   **Tipo:** Serverless Network Endpoint Group (NEG).
*   **Alvo:** O serviço Cloud Run `jor-mcp`.
*   **Protocolo:** HTTP/2 (Recomendado para streaming SSE).
*   **Timeout:** Certifique-se de que o timeout do backend esteja configurado alto o suficiente (ex: 3600 segundos) para que as conexões Server-Sent Events (SSE) não caiam prematuramente.

### 2.2 Backend Bucket: Frontend (GCS)
*   **Tipo:** Backend Bucket.
*   **Alvo:** O bucket GCS contendo a exportação estática do Next.js (`gs://nome-do-seu-bucket`).
*   **Cloud CDN:** Habilite o Cloud CDN neste backend bucket para armazenar ativos estáticos globalmente em cache.

## 3. Mapa de URL (Regras de Roteamento)
O núcleo do load balancer é o Mapa de URL. Configure as regras de Host e Caminho da seguinte forma:

| Host | Caminho | Backend |
| :--- | :--- | :--- |
| `jormcp.ambiental.media` | `/mcp/*` | API (Serverless NEG) |
| `jormcp.ambiental.media` | `/api/oauth/*` | API (Serverless NEG) |
| `jormcp.ambiental.media` | `/.well-known/*` | API (Serverless NEG) |
| `jormcp.ambiental.media` | `/*` (Padrão) | Frontend (Backend Bucket) |

## 4. Políticas de Segurança & CORS
*   **CORS:** Certifique-se de que o Load Balancer esteja configurado para permitir que solicitações preflight `OPTIONS` cheguem ao serviço Cloud Run, para que o backend Python possa responder com os cabeçalhos `Access-Control-Allow-Origin` corretos para o endpoint `/api/oauth/approve`.
*   **Cloud Armor (Opcional / Avançado):** Você pode anexar uma política WAF do Google Cloud Armor ao Serviço de Backend da API para bloquear IPs maliciosos antes que eles atinjam o Cloud Run. 
    *   *Aviso de FinOps:* Diferente do Cloud Run e Firestore que escalam para zero, o Cloud Armor introduz custos mensais fixos (aproximadamente $5-$10/mês de taxa base). Como o Jor-MCP inclui limitação de taxa em nível de aplicativo via Firestore, o Cloud Armor só é necessário se você espera ataques DDoS volumétricos severos.