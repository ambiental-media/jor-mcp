# ADR 007: Estratégia de Hospedagem Frontend (Bucket GCS)

## 1. Contexto
O projeto Jor-MCP exige a hospedagem da landing page `jor-mcp-site` (Next.js) e da interface interativa de consentimento OAuth 2.1 (`/authorize`) no mesmo domínio personalizado (`jor-mcp.ambiental.media`) da API backend Python FastMCP. Utilizamos um Global External Application Load Balancer do Google Cloud como ponto de entrada principal para gerenciar TLS e roteamento de URL.

## 2. Alternativas Consideradas

### 2.1 Internet NEG para Provedor Legado (Hostinger)
*   **Abordagem:** Rotear o tráfego `/*` do Load Balancer do GCP para um servidor Hostinger externo onde reside a landing page legada, e rotear `/mcp/*` para o Cloud Run.
*   **Rejeitado porque:** 
    *   *Incompatibilidade TLS/SNI:* Fazer proxy de tráfego HTTPS para ambientes de hospedagem compartilhada frequentemente falha devido ao Server Name Indication (SNI) e incompatibilidades de certificados.
    *   *Violação de FinOps:* Seríamos cobrados pela largura de banda de saída (egress) premium do GCP apenas para fazer proxy de HTML estático da Hostinger de volta para o usuário.
    *   *Confiabilidade:* Introduz pontos de falha entre provedores.

### 2.2 Cloud Run (Node.js)
*   **Abordagem:** Implantar a aplicação Next.js como um contêiner Node.js dinâmico no Cloud Run junto com o servidor Python.
*   **Rejeitado porque:** A landing page e a UI de consentimento OAuth (`/authorize`) podem ser compiladas em HTML/JS/CSS puramente estáticos usando o Next.js `output: 'export'`. Executar uma instância de computação para ativos estáticos viola os princípios de eficiência de FinOps.

## 3. Decisão
Hospedaremos a exportação estática do Next.js (diretório `out/`) em um **Google Cloud Storage (GCS) Bucket** configurado como um Backend Bucket no Load Balancer Global existente, e ativaremos o **Cloud CDN**.

## 4. Consequências
*   **Custo:** Custos de hospedagem quase zero (centavos por mês para armazenamento e cache CDN), maximizando a eficiência de FinOps.
*   **Confiabilidade:** 99,999% de disponibilidade para a interface do frontend, completamente desacoplada das instâncias de computação em Python.
*   **CI/CD:** O pipeline de implantação deve ser atualizado para incluir uma etapa que faça o upload dos ativos estáticos para o bucket GCS (`gsutil rsync` ou uma GitHub Action equivalente) em vez de depender de implantações de contêineres padrão.
*   **CORS:** O frontend estático fará chamadas AJAX do lado do cliente para o backend Python (ex: `POST /api/oauth/approve`), exigindo que o backend configure estritamente o Cross-Origin Resource Sharing (CORS).