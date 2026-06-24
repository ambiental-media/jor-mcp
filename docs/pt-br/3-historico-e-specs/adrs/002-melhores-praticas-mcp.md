# Spike Pré-POC: Melhores Práticas MCP e Telemetria

## 1. Objetivo
Estabelecer as melhores práticas para a construção de um servidor MCP, com foco em observabilidade (telemetria), tratamento de erros e otimização da janela de contexto do LLM.

## 2. Estratégia de Telemetria (OpenTelemetry)

Uma infraestrutura de monitoramento robusta é crítica para garantir a saúde e o desempenho do servidor MCP.

*   **Abordagem:** Utilizaremos **OpenTelemetry (OTel)**.
*   **Instrumentação:** Para minimizar as mudanças no código, contaremos com a **Instrumentação Automática** (ex: `opentelemetry-instrumentation-fastapi`, `httpx`, padrões do `google-cloud-firestore`). A instrumentação manual será usada apenas para métricas de domínio altamente específicas (ex: rastreamento de uso de tokens, se necessário).
*   **Exportação:** Para simplificar a implantação no Cloud Run e evitar gerenciar um contêiner sidecar (OTel Collector), usaremos **SDK Exporters** diretos (`opentelemetry-exporter-gcp-monitoring` e `opentelemetry-exporter-gcp-trace`).
*   **Métricas Principais:**
    *   *Latência:* Rastreada via Histogramas (p50, p95, p99).
    *   *Disponibilidade/Erros:* Rastreada via códigos de status HTTP (2xx vs 5xx) e tipos de exceção.

## 3. Padrões de Tratamento de Erros

Códigos de erro HTTP padrão são insuficientes para agentes de IA, pois o agente precisa de compreensão semântica de *por que* uma operação falhou para ajustar seu comportamento.

*   **Prática:** Quando uma ferramenta interna falha (ex: um artigo do WordPress não é encontrado, ou um repositório GitHub está inacessível), o servidor deve lançar um `ToolError` (específico do framework FastMCP).
*   **Dicas Semânticas:** A mensagem de erro deve conter instruções claras e legíveis por humanos em português, guiando o LLM sobre como se recuperar. Por exemplo: *"Artigo não encontrado com este ID. Tente utilizar a ferramenta search_content para buscar por palavras-chave."*

## 4. Gerenciamento de Contexto (Sustentabilidade de Tokens)

LLMs têm janelas de contexto limitadas e cobram por token. O servidor MCP deve ser responsável por minimizar o payload que retorna.

*   **Prática - Filtragem Server-Side:** O servidor deve fazer o trabalho pesado. Em vez de retornar HTML bruto do WordPress, o servidor deve implementar um parser de HTML para remover tags, shortcodes e elementos de navegação, retornando apenas o texto essencial do artigo.
*   **Prática - Paginação e Limites:** Ferramentas como `list_latest_news` devem aplicar limites superiores estritos (ex: máximo de 20 resultados) para evitar inundar acidentalmente o contexto do LLM.
*   **Prática - Baixa Contagem de Ferramentas (Low Tool Count):** Evite expor operações de banco de dados granulares (CRUD). Exponha ferramentas compostas e de alto nível (como uma busca unificada) para reduzir a carga cognitiva e a sobrecarga de tokens do agente ao decidir qual ferramenta usar.