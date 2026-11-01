<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# ADR 009: Allowlist de Host de Redirecionamento OAuth

## 1. Contexto
Clientes MCP nativos usam o Registro Dinâmico de Cliente (RFC 7591), que é intencionalmente aberto para que o Claude Desktop conecte sem provisionamento manual. O registro aberto também permite que qualquer pessoa registre um cliente cujo `redirect_uris` aponta para um host sob seu controle.

O fluxo de consentimento então vira um caminho de roubo de token: o atacante registra `https://atacante.example/cb` junto com um desafio PKCE que ele mesmo gerou, envia esse link de consentimento para a vítima e recebe o código de autorização quando ela clica em Permitir. O PKCE não impede isso, porque o atacante é dono do verifier. A tela de consentimento mostra apenas `client_name`, que o atacante também controla.

A coleção `oauth_clients` de produção mostra que o registro não é só loopback: 185 clientes redirecionam para `localhost` (75), `claude.ai` (100), `chatgpt.com` (7) e `www.braintrust.dev` (3). Uma regra apenas loopback quebraria todos os conectores remotos.

## 2. Decisão
O registro continua aberto, mas os hosts de redirecionamento são restritos:

*   Hosts de loopback (`localhost`, `127.0.0.1`, `::1`) são sempre aceitos, após a normalização existente, e podem usar `http` simples porque a requisição nunca sai do dispositivo (RFC 8252).
*   Qualquer outro host precisa estar em `OAUTH_ALLOWED_REDIRECT_HOSTS` (variável de ambiente separada por vírgula) e usar `https`.
*   A regra é aplicada duas vezes: em `POST /api/oauth/register` (`400 invalid_redirect_uri`) e ao resolver o redirecionamento em `POST /api/oauth/approve` (`400 invalid_request`). A segunda checagem cobre clientes registrados antes da allowlist existir.
*   A implantação de referência semeia `claude.ai,chatgpt.com,www.braintrust.dev`. Um fork configura os clientes que realmente suporta; com a variável vazia, apenas clientes loopback concluem o consentimento.

## 3. Alternativas Consideradas

### 3.1 Registro apenas loopback
Mais simples e mais forte, mas quebra os 110 clientes remotos observados em produção. Rejeitado.

### 3.2 Registro protegido (initial access token ou software statement)
O modo protegido do RFC 7591, mas remove a experiência de zero configuração que o ADR 006 existe para oferecer. Rejeitado para clientes desktop; pode ser adicionado depois para provisionamento corporativo.

### 3.3 Apenas exibir o host de redirecionamento na tela de consentimento
Informativo, mas não impede o usuário que clica mesmo assim. Rejeitado como controle único.

### 3.4 Allowlist por prefixo de caminho
Entradas como `claude.ai/api/mcp/auth_callback` são mais estritas que allowlist de host, mas quebram sempre que o provedor muda o caminho de callback. Mantido como endurecimento futuro caso algum domínio permitido exponha um open redirect.

## 4. Consequências
*   O atacante não consegue mais registrar callback em um host que o operador não controla, e documentos maliciosos pré-existentes são recusados no consentimento.
*   Clientes remotos registrados em `http` simples também são recusados. Os dados de produção têm apenas registros remotos `https`, então nenhum cliente ativo quebra.
*   Suportar um novo conector remoto passa a ser mudança explícita de configuração e redeploy, não capacidade automática.
*   Um host ausente aparece como 400 claro com `invalid_redirect_uri` / `invalid_request`, não como falha silenciosa.
*   Hosts rejeitados são registrados em log (apenas o host, nunca a URI completa ou um token).
*   Nenhuma mudança de schema no Firestore; documentos de clientes existentes permanecem como estão.
*   A proliferação de registros não muda: o limitador por IP controla a taxa, mas clientes duplicados se acumulam. A limpeza de documentos antigos em `oauth_clients` continua como acompanhamento separado.

## 5. Migração
1. Implante o backend com `OAUTH_ALLOWED_REDIRECT_HOSTS` cobrindo todos os hosts usados pelos clientes suportados.
2. Verifique um consentimento localhost e um remoto de ponta a ponta.
3. A reversão é a imagem anterior; remover apenas a variável volta ao modo loopback-only, que quebra conectores remotos.
