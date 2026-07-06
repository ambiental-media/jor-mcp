<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Conectando a LLMs

Para conectar o Claude Desktop (ou outros agentes compatíveis com MCP) ao servidor Jor-MCP da Ambiental Media, siga estas instruções simples passo a passo.

O processo de conexão foi totalmente modernizado e agora é concluído de forma totalmente interativa por meio de uma interface gráfica (UI) no navegador, garantindo uma experiência contínua para jornalistas e usuários não técnicos.

---

## 1. Configure o Claude Desktop

Primeiramente, configure o Claude Desktop para reconhecer o servidor Jor-MCP:

1. Abra o Claude Desktop.
2. Vá para **Settings** > **Developer** > **Edit Config**.
3. Adicione o servidor Jor-MCP ao seu arquivo de configuração (`claude_desktop_config.json`):

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

4. Salve o arquivo e reinicie o Claude Desktop.

---

## 2. Passo a Passo do Fluxo de Autorização no Navegador

Na primeira vez que você interagir com as ferramentas do Jor-MCP no Claude, será solicitado que você se autentique:

*   **Passo 1:** Acessando o Portal de Consentimento (Imagem 01)
    O Claude abrirá automaticamente uma janela pop-up do navegador apontando para o portal de autorização.
    ![Passo 1 - Tela Inicial do Portal](/assets/how-to-connect-01.png)

*   **Passo 2:** Login com Google SSO (Imagens 02 e 03)
    Selecione seu método de login via Google SSO. Use o endereço de e-mail que foi previamente cadastrado e autorizado pela Ambiental Media.
    ![Passo 2 - Entrada no Google](/assets/how-to-connect-02.png)
    ![Passo 3 - Seleção de Conta](/assets/how-to-connect-03.png)

*   **Passo 3:** Revisar Solicitação de Permissões (Imagem 04)
    Após efetuar o login, o portal exibirá um cartão de consentimento listando as permissões exatas solicitadas pelo cliente (Claude Desktop).
    ![Passo 4 - Revisando Consentimento](/assets/how-to-connect-04.png)

*   **Passo 4:** Aprovar a Conexão (Imagem 05)
    Clique no botão **"Authorize"** para confirmar a concessão de acesso ao Claude.
    ![Passo 5 - Concedendo Consentimento](/assets/how-to-connect-05.png)

*   **Passo 5:** Conexão Estabelecida com Sucesso (Imagens 06 e 07)
    O portal processará o consentimento de forma segura e exibirá a confirmação de que o vínculo foi realizado com sucesso.
    ![Passo 6 - Conexão Autorizada](/assets/how-to-connect-06.png)
    ![Step 7 - Retornando ao Claude](/assets/how-to-connect-07.png)

Depois disso, você já pode fechar a aba do navegador e retornar ao Claude.

---

## 3. Autenticação Persistente

Uma vez concluído o login inicial, sua autenticação é persistente. O Claude Desktop gerencia automaticamente a renovação do token em segundo plano usando *Refresh Tokens* de longa duração. Você não precisará se autenticar novamente nem reconfigurar suas configurações manualmente, mesmo se reiniciar o Claude Desktop diariamente.

---

## 4. Upgrades de Nível (Planos Pagos)

Se você negociou um plano pago (nível `Pro`) com a Ambiental Media:
1. Sua conta será atualizada por nossos administradores via **Console de Administração do Jor-MCP**.
2. Nenhuma ação é necessária da sua parte; na próxima vez que você usar o Jor-MCP, seus limites de solicitação aumentarão automaticamente para a cota do nível `Pro`.
```