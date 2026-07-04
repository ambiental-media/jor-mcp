# Roteiro do Projeto Jor-MCP

Este documento descreve os objetivos de alto nível e as próximas funcionalidades do projeto Jor-MCP. Ele oferece transparência sobre nossas áreas de foco atuais e o que os usuários podem esperar no futuro.

## Atualmente em Desenvolvimento 🏗️
*   **Integração Nativa MCP OAuth 2.1:** Transição de chaves de API estáticas para um fluxo OAuth totalmente interativo usando PKCE para conexões de configuração zero no Claude Desktop.
*   **Desenvolvimento do Portal Next.js:** Construção do `jor-mcp-site` para lidar com o consentimento do usuário e autenticação via Google SSO.
*   **Marco Legal:** Estabelecer a base legal do projeto, incluindo a definição da Licença Open Source, a elaboração dos Termos de Uso para a instância pública e a criação da Política de Privacidade para o tratamento de dados dos usuários.

## Próximos Passos (Curto Prazo) ⏳
*   **Rate Limiting Baseado em Tokens e Quotas Semanais:** Migrar de limites baseados em requisições para limites baseados no consumo de tokens, alterando o ciclo de reset de mensal para semanal para um controle mais preciso e métricas de faturamento ajustadas.
*   **Expansão da Autenticação Firebase:** Explorar a configuração do Firebase para habilitar métodos de autenticação adicionais, como Google, OpenID Connect (OIDC), SAML, Microsoft e Apple.
*   **Validação da Replicação:** Selecionar uma organização parceira para replicar o Jor-MCP em sua própria infraestrutura. Forneceremos suporte prático durante o processo e utilizaremos os aprendizados para refinar o manual de replicação (playbook) e a documentação definitiva.

## Visão de Futuro (Longo Prazo) 🚀
(A definir)

---
*Nota: Este roteiro é um documento vivo e sujeito a alterações com base no feedback da comunidade e nas prioridades do projeto.*
