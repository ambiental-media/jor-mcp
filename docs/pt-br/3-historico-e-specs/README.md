<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Jornada do Projeto

O projeto `jor-mcp` nasceu de uma visão de fornecer às organizações de jornalismo investigativo uma infraestrutura segura, modular e replicável para dados jornalísticos estruturados.

## Financiamento & Apoio
Este projeto foi possível graças ao apoio generoso de duas grandes iniciativas globais de jornalismo:

*   **[JournalismAI Innovation Challenge](https://www.journalismai.info/programmes/innovation):** Apoiado pela "JournalismAI" (um projeto da POLIS Journalism na LSE) e pela "Google News Initiative", visando o ecossistema jornalístico global.
*   **[Codesinfo](https://codesinfo.com.br/en/home-english/):** Apoiado pelo "Projor" e pela "Google News Initiative", visando o ecossistema jornalístico brasileiro.

## Missão do Projeto
Nossa missão principal é reduzir as barreiras técnicas para redações, fornecendo código de código aberto, guias de adoção e uma página de apresentação pública para facilitar a integração de IA com conteúdo editorial, garantindo que as redações possam pesquisar, recuperar e analisar seus dados proprietários de forma segura e ética.

## Evolução do Projeto

### Fase 1: Fundação e Governança (Início de 2026)
O projeto começou focando na consolidação do planejamento estratégico e investigação técnica. Estabelecemos fluxos de trabalho rigorosos usando ClickUp, rastreando mais de 80 tickets acionáveis, e iniciamos uma série de "spikes" técnicos para mapear recursos de MCP, definir estratégias de telemetria (OpenTelemetry) e estabelecer melhores práticas de código aberto. Um resultado crítico foi a definição de nossos requisitos de governança e legais, garantindo o alinhamento com os regulamentos de proteção de dados e proteção de propriedade intelectual para conteúdo jornalístico.

### Fase 2: Mentoria e Pivotagem Arquitetural (Primavera 2026)
O projeto passou por uma evolução arquitetural significativa após a mentoria de Abdullah Enes Gules (Context7/Upstash). Esta fase marcou o pivô para a arquitetura definitiva da v1:
*   **Statelessness:** Adoção de uma aplicação FastMCP totalmente stateless no Google Cloud Run.
*   **OAuth 2.1 (PKCE):** Pivô de chaves de API estáticas para um fluxo OAuth interativo e compatível com o padrão para conexões perfeitas no Claude Desktop.
*   **Low Tool Count:** Adoção de uma filosofia de ferramentas de granulação grossa para otimizar a janela de contexto e o desempenho do LLM.
*   **Observabilidade:** Integração da auto-instrumentação OpenTelemetry desde o início para rastreamento de nível de produção.

### Fase 3: Prontidão para Lançamento e Sustentabilidade (Final da Primavera 2026)
Nesta etapa, o projeto transitou da P&D pura para a prontidão de lançamento. Finalizamos a marca e a identidade visual—projetadas para representar o fluxo e processamento de dados—e construímos o portal `jor-mcp-site` para preencher a lacuna entre a infraestrutura técnica e o consentimento do usuário. Também estabelecemos fluxos de trabalho de integração B2B, permitindo que as redações negociem planos pagos diretamente, seguidos pelo provisionamento manual de níveis (Básico vs. Pro) no Firestore pelos administradores.

## Conteúdo
- [Cronograma do Projeto](cronograma-do-projeto.md)
- [Specs](specs/)
- [ADRs](adrs/)
- [Relatórios](relatorios/)
- [Roteiro](roadmap.md)
- [Identidade Visual](identidade-visual.md)