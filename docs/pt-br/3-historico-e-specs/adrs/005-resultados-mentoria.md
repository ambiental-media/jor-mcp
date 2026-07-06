<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Resultados da Mentoria Técnica

**Data:** Fase de Planejamento Pré-v1
**Mentor:** Abdullah Enes Gules (Contribuinte Principal, Context7 MCP / Upstash)

## 1. Visão Geral
Após a POC, a equipe engajou-se em uma sessão de mentoria técnica para revisar a arquitetura e alinhá-la com as melhores práticas da indústria para servidores MCP. A sessão resultou em vários pivôs arquiteturais críticos que definem a especificação da v1.

## 2. Decisões Arquiteturais Principais

### 2.1 Arquitetura e Segurança
*   **Statelessness:** Reafirmou fortemente a necessidade de um servidor stateless (sem estado) para garantir escalabilidade perfeita no Google Cloud Run.
*   **Integração OAuth:** Dado que o cliente LLM final provavelmente será baseado na web, a mentoria recomendou fortemente desacoplar a autenticação da lógica principal e migrar para o **OAuth 2.0** padrão.
*   *Material de referência fornecido:* Blog da Upstash sobre Implementação MCP OAuth.

### 2.2 Otimização de Desempenho e Ferramentas
*   **Filosofia Low Tool Count:** O mentor enfatizou a exposição de um número muito pequeno e altamente abstrato de ferramentas.
    *   *Fundamentação:* Alta granularidade confunde o LLM, desperdiça tokens da janela de contexto com descrições excessivas de ferramentas e degrada o desempenho.
*   **Responsabilidade Server-Side:** O servidor deve fazer o trabalho pesado (agregação, limpeza e formatação de dados) antes de enviar dados ao LLM. Isso reduz a carga cognitiva no modelo e previne alucinações.

### 2.3 System Prompts
*   **Instruções Embutidas:** Recomendou utilizar as capacidades de inicialização do servidor para embutir "System Prompts" (`FastMCP(instructions=...)`). Estes instruem o LLM sobre exatamente como se comportar ao interagir com as ferramentas de jornalismo, estabelecendo limites (guardrails).
    *   *Material de referência fornecido:* Código-fonte do Context7 (`src/index.ts`).

### 2.4 Busca Semântica (Adiada)
*   **Discussão sobre Vector Search:** O uso de Bancos de Dados Vetoriais (Busca Semântica) foi discutido para melhorar a precisão da busca sobre a busca textual básica da API REST.
*   *Resultado:* Embora valioso, a equipe decidiu **adiar** a integração de banco de dados vetorial da arquitetura v1 para priorizar a ingestão em tempo real (chamadas REST stateless) e minimizar a complexidade da infraestrutura no lançamento inicial.

## 3. Impacto na Especificação v1
Esses resultados de mentoria informaram diretamente a [SPEC-001-v1-core](../specs/SPEC-001-v1-core.md), levando à adoção do Firebase Auth (OAuth), Google Cloud Firestore (para limitação de taxa stateless), o limite estrito de 3 ferramentas e a inclusão de instruções explícitas do servidor.
