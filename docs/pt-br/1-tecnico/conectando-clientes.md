<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Conectando a LLMs

Para conectar o Claude Desktop (ou outros agentes compatíveis com MCP) ao servidor Jor-MCP da Ambiental Media, siga estes passos simples e não técnicos:

### 1. Configure o Claude Desktop
1. Abra o Claude Desktop e vá para **Settings** > **Developer** > **Edit Config**.
2. Adicione o servidor Jor-MCP ao seu arquivo de configuração (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jor-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/inspector",
        "https://jormcp.ambiental.media/mcp/sse"
      ]
    }
  }
}
```
3. Salve o arquivo e reinicie o Claude Desktop.

### 2. Autenticação Interativa
Na primeira vez que você interagir com as ferramentas do Jor-MCP no Claude, você será solicitado a se autenticar:
1. O Claude disparará automaticamente uma janela pop-up do navegador.
2. O navegador navegará para a tela de login do **Portal Jor-MCP**.
3. Faça login com as credenciais da sua conta Ambiental Media.
4. Uma vez logado, clique em **"Authorize"** para conceder ao Claude acesso à sua conta.
5. O navegador redirecionará de volta ao Claude, completando a conexão com segurança.

### 3. Autenticação Persistente
Uma vez concluído o login inicial, sua autenticação é persistente. O Claude Desktop gerencia automaticamente a renovação do token em segundo plano usando *Refresh Tokens* de longa duração. Você não precisará se autenticar novamente nem reconfigurar suas configurações manualmente, mesmo se reiniciar o Claude Desktop diariamente.

### 4. Upgrades de Nível (Planos Pagos)
Se você negociou um plano pago (nível `Pro`) com a Ambiental Media:
1. Sua conta será atualizada por nossos administradores via **Console de Administração do Jor-MCP**.
2. Nenhuma ação é necessária da sua parte; na próxima vez que você usar o Jor-MCP, seus limites de solicitação aumentarão automaticamente para a cota do nível `Pro`.
