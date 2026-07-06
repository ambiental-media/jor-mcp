<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Conectando a LLMs

Para conectar o Claude Desktop (ou outros agentes compatíveis com MCP) ao servidor Jor-MCP da Ambiental Media, siga estas instruções simples passo a passo.

O processo de conexão foi totalmente modernizado e é concluído inteiramente por meio da interface interativa do Claude e do seu navegador, garantindo uma experiência contínua.

---

## Passo a Passo do Fluxo de Autorização no Navegador

Siga estes passos com as telas de interface correspondentes para criar sua conexão segura:

### Passo 1: Abrir o Menu de Personalização
No Claude Desktop, clique no botão **"Customize"** no canto inferior esquerdo para abrir o menu de configurações e opções.

![Passo 1 - Menu de Personalização do Claude](/assets/how-to-connect-01.png)

### Passo 2: Adicionar Conector Personalizado
Na barra lateral de personalização, procure a seção **"Connectors"**. Clique em **"Add"** e selecione **"Add Custom Connector"**.

![Passo 2 - Adicionar Conector Personalizado](/assets/how-to-connect-02.png)

### Passo 3: Inserir Detalhes do Conector
Digite `jor-mcp` como o **Connector Name** (Nome do Conector) e digite `https://jormcp.ambiental.media/mcp/sse` como o **Connector URL** (URL do Conector). Assim que os dois campos estiverem preenchidos, clique no botão **"Add"**.

![Passo 3 - Inserir Nome e URL](/assets/how-to-connect-03.png)

### Passo 4: Iniciar Conexão
Na página do conector recém-criado, clique no botão **"Connect"** para iniciar o fluxo de autorização.

![Passo 4 - Iniciar Conexão](/assets/how-to-connect-04.png)

### Passo 5: Login via Google SSO
O Claude o redirecionará para a tela de login do portal de consentimento seguro do **Jor-MCP**. Clique no botão do Google e selecione ou insira as credenciais da sua conta do Google autorizada/cadastrada pela Ambiental Media para fazer login.

![Passo 5 - Login do Google](/assets/how-to-connect-05.png)

### Passo 6: Conceder Consentimento
Uma vez logado, revise as permissões de acesso solicitadas no cartão de consentimento e clique em **"Allow Access"** (ou **"Permitir Acesso"**) para autorizar com segurança o Claude Desktop a consultar a base de dados do Jor-MCP.

![Passo 6 - Autorizar no Portal](/assets/how-to-connect-06.png)

### Passo 7: Conexão Finalizada
Sua autorização foi verificada e a conexão está estabelecida com segurança. Você já pode fechar a janela do navegador.

![Passo 7 - Pronto para Usar](/assets/how-to-connect-07.png)

Retorne ao Claude Desktop. Você já está pronto para realizar buscas, buscar artigos e analisar conjuntos de dados de forma dinâmica!

---

## Autenticação Persistente

Uma vez concluído o login inicial, sua autenticação é persistente. O Claude Desktop gerencia automaticamente a renovação do token em segundo plano usando *Refresh Tokens* de longa duração. Você não precisará se autenticar novamente nem reconfigurar suas configurações manualmente, mesmo se reiniciar o Claude Desktop diariamente.

---

## Upgrades de Nível (Planos Pagos)

Se você negociou um plano pago (nível `Pro`) com a Ambiental Media:
1. Sua conta será atualizada por nossos administradores via **Console de Administração do Jor-MCP**.
2. Nenhuma ação é necessária da sua parte; na próxima vez que você usar o Jor-MCP, seus limites de solicitação aumentarão automaticamente para a cota do nível `Pro`.
