# ADR 006: Estratégia de Implementação do MCP OAuth 2.1

## 1. O "Porquê" (Contexto)
*   **Objetivo:** Fornecer uma experiência de login "zero-configuração" para jornalistas não técnicos usando o Claude Desktop.
*   **Problema:** O Claude Desktop não suporta logins interativos via navegador nativamente, a menos que o servidor implemente o protocolo estrito MCP OAuth 2.1 (PKCE + Registro Dinâmico de Cliente).
*   **Solução:** Estamos migrando de chaves de API estáticas / JWTs simples para um fluxo nativo MCP OAuth 2.1 completo, usando um padrão de "Proxy Defensivo".

## 2. O que Mudou na Arquitetura?
*   **Arquitetura Antiga:** `jor-mcp` (Python) era um servidor de recursos simples que apenas validava JWTs do Firebase.
*   **Nova Arquitetura (Multi-Repo):** 
    *   `jor-mcp` (Backend Python): Agora atua como um **Proxy OAuth**. Ele intercepta solicitações OAuth do Claude, normaliza-as e comunica-se com o Firebase para emitir tokens.
    *   `jor-mcp-site` (Frontend Next.js): Agora atua como o **Portal de Consentimento**. Ele lida com o login real do usuário e a tela de "Conceder Acesso ao Claude".

## 3. Como o Novo Fluxo Funciona (Resumo Rápido)
1.  **Descoberta:** O Claude acessa o `jor-mcp` e é instruído sobre onde se autenticar.
2.  **Registro (DCR):** O Claude se registra no `jor-mcp`.
3.  **Consentimento:** O Claude abre o navegador do usuário em `jor-mcp-site/authorize`. O usuário faz login via Firebase e clica em "Permitir".
4.  **Troca:** O navegador redireciona de volta para o Claude com um código. O Claude troca esse código com o `jor-mcp` por tokens de longa duração do Firebase.

## 4. Como Implementaremos (Tarefas de Engenharia)

### Time de Backend (`jor-mcp` - Python)
*   **Endpoints para Criar:** 
    *   `/.well-known/oauth-authorization-server` (Metadados)
    *   `/api/oauth/register` (Registro Dinâmico de Cliente)
    *   `/api/oauth/token` (Troca de Token & validação PKCE)
*   **Pontos Críticos a Resolver:**
    *   *Normalização de Loopback:* Deve normalizar forçadamente incompatibilidades entre `localhost` e `127.0.0.1` do Claude.
    *   *Forçar Cliente Público:* Deve forçar `token_endpoint_auth_method` para `"none"`.

### Time de Frontend (`jor-mcp-site` - Next.js)
*   **Páginas para Criar:**
    *   `/authorize`: A interface que captura `client_id` e `code_challenge`, força o login no Firebase e faz um POST para o backend Python para obter um código de autenticação.
    *   `/admin`: Painel B2B para a equipe da Ambiental Media atualizar usuários no Firestore de `tier: basic` para `tier: pro`.

### Banco de Dados (Firestore)
*   Adicionar novas coleções: `oauth_clients` (para armazenar instâncias registradas do Claude) e `oauth_codes` (para armazenar desafios PKCE temporários).
