<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Roteiro do Projeto Jor-MCP

Este documento descreve os objetivos de alto nível e as próximas funcionalidades do projeto Jor-MCP. Ele oferece transparência sobre nossas áreas de foco atuais e o que os usuários podem esperar no futuro.

## Atualmente em Desenvolvimento 🏗️
*   **Integração Nativa MCP OAuth 2.1:** Transição de chaves de API estáticas para um fluxo OAuth totalmente interativo usando PKCE para conexões de configuração zero no Claude Desktop.
*   **Desenvolvimento do Portal Next.js:** Construção do `jor-mcp-site` para lidar com o consentimento do usuário e autenticação via Google SSO.
*   **Hardenização de Segurança e Infraestrutura:** Auditoria e correção de vulnerabilidades no portal frontend (XSS, Open Redirect), implementação de limitação de taxa por IP no backend para rotas públicas e aplicação do princípio do menor privilégio (IAM) na infraestrutura Cloud Run.
*   **Marco Legal:** Estabelecer a base legal do projeto, incluindo a definição da Licença Open Source, a elaboração dos Termos de Uso para a instância pública e a criação da Política de Privacidade para o tratamento de dados dos usuários.

## Próximos Passos (Curto Prazo) ⏳
*   **Rate Limiting Baseado em Tokens e Quotas Semanais:** Migrar de limites baseados em requisições para limites baseados no consumo de tokens, alterando o ciclo de reset de mensal para semanal para um controle mais preciso e métricas de faturamento ajustadas.
*   **Expansão da Autenticação Firebase:** Explorar a configuração do Firebase para habilitar métodos de autenticação adicionais, como Google, OpenID Connect (OIDC), SAML, Microsoft e Apple.
*   **Validação da Replicação (Programa Piloto):** Selecionar e colaborar com uma organização de jornalismo parceira piloto inicial para implantar o `jor-mcp` em sua infraestrutura. Ofereceremos suporte dedicado, usando as lições aprendidas para gerar um **Playbook de Replicação** padronizado, além de blueprints de **Infraestrutura como Código (IaC)** e **Configuração como Código (CaC)** para tornar implantações futuras livres de atritos. Organizações parceiras interessadas são convidadas a entrar em contato conosco para participar desta rodada piloto inicial.
*   **Modelos de Sustentabilidade:** Exploração de modelos de sustentabilidade e comercialização para o JOR-MCP, visando garantir sua continuidade e ampliar seu potencial de impacto.
*   **Sessões de Teste com Usuários:** Organizar e conduzir sessões de teste controladas com usuários selecionados para coletar feedback estruturado, identificar bugs e descobrir oportunidades de funcionalidades. Relatórios de teste serão gerados para orientar os próximos ciclos de iteração do projeto.

## Visão de Futuro (Longo Prazo) 🚀
(A definir)

---
*Nota: Este roteiro é um documento vivo e sujeito a alterações com base no feedback da comunidade e nas prioridades do projeto.*
