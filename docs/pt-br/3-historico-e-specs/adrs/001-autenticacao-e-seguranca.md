<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Spike Pré-POC: Autenticação e Segurança

## 1. Objetivo
Determinar a estratégia ideal para autenticar clientes de LLM e proteger o servidor Jor-MCP.

## 2. Contexto
O servidor Jor-MCP será exposto publicamente (via Cloud Run ou Load Balancer) para servir conteúdo a vários agentes de IA. Ele requer um mecanismo para verificar a identidade do cliente solicitante e aplicar limites de uso para evitar abusos e gerenciar custos.

## 3. Estratégias de Autenticação Avaliadas

### 3.1 API Keys (Simétrica)
*   **Conceito:** O servidor e o cliente compartilham uma string secreta.
*   **Prós:** Extremamente simples de implementar.
*   **Contras:** Difícil gerenciar a rotação; se comprometida, todo o acesso é violado. Não escala facilmente para cenários multi-tenant B2C.

### 3.2 JSON Web Tokens (JWT) - Simétrico (HS256)
*   **Conceito:** O servidor gera e assina um token usando uma chave secreta. O cliente passa este token no cabeçalho `Authorization: Bearer`.
*   **Prós:** Stateless; pode codificar claims básicas (expiração, ID do usuário).
*   **Contras:** Exige que o servidor Jor-MCP gerencie logins de usuários e distribuição de segredos.

### 3.3 OAuth 2.0 Resource Server (Assimétrico - RS256/JWKS)
*   **Conceito:** Um Identity Provider (IdP) dedicado como Firebase Auth, Auth0 ou Clerk lida com o registro e login do usuário. Ele emite um JWT assinado com uma chave privada. O servidor Jor-MCP busca as chaves públicas do IdP (JWKS) para verificar a assinatura do token.
*   **Prós:** Desacopla completamente a lógica de autenticação do servidor MCP. Altamente escalável. Suporte nativo para clientes web front-end.
*   **Contras:** Pequeno aumento na complexidade inicial de configuração.

## 4. Decisão Arquitetural: Segurança & Auth

1.  **Autenticação:** O projeto adota o modelo **OAuth 2.1 (Resource Server + Proxy)**. Utilizamos o **Firebase Auth / Google Identity Platform** como Provedor de Identidade. Para resolver peculiaridades de clientes MCP (como incompatibilidades entre localhost/127.0.0.1 e conformidade com DCR), o backend Python atua como um **Proxy Defensivo OAuth**, normalizando as requisições de DCR e Troca de Token antes de interagir com o Firebase para emitir *Access Tokens* de curta duração e *Refresh Tokens* de longa duração.
2.  **Limitação de Taxa (Rate Limiting):** Prevenção obrigatória contra abusos. Mudamos do **GCP Memorystore (Redis)** para o **Google Cloud Firestore** para eliminar custos de provisionamento de base e manter uma arquitetura totalmente serverless.
3.  **Persistência (Gerenciamento de Sessão):** Ao implementar *Refresh Tokens* padrão OAuth 2.1, garantimos uma experiência de "Login Único" para jornalistas no Claude Desktop. O Claude Desktop gerencia automaticamente a renovação do token em segundo plano, mantendo a autenticação persistente por semanas sem intervenção do usuário.
4.  **Autorização (Níveis):** O limitador de taxa do Firestore lê as *claims* de `tier` (nível) dos JWTs emitidos pelo Firebase para aplicar cotas de tráfego diferenciadas (Básico vs. Pro).
