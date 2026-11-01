<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# ADR 008: Portal de Consentimento Autocontido

## 1. Contexto
A interface de consentimento OAuth 2.1 vivia em um repositório Next.js separado e era implantada no mesmo bucket do Google Cloud Storage da landing page desse repositório. Duas consequências:

*   Replicar o Jor-MCP exigia clonar e implantar um segundo repositório, então este repositório não bastava para provisionar um servidor funcional.
*   Os dois repositórios escreviam no mesmo bucket. Qualquer um executando `rsync --delete-unmatched-destination-objects` podia apagar os objetos do outro, e os dois builds Next.js competiam pelo caminho `/_next`.

O backend já é dono da descoberta, do registro dinâmico de clientes, da aprovação de consentimento e da troca de tokens. A interface de consentimento é o único frontend de que o servidor MCP precisa.

## 2. Decisão
Mover a interface de consentimento para este repositório como `portal/`, compilada como exportação estática Next.js e servida a partir de um bucket GCS próprio, atrás do Cloud CDN.

O **perfil standalone** é o padrão e o único caminho de replicação documentado: o bucket do portal é o backend padrão do load balancer, os ativos ficam em `/_next` e nenhum outro site está envolvido.

Um **perfil de sobreposição** existe para implantações que já servem outro site no mesmo host. Ele mantém esse site como backend padrão, roteia quatro prefixos de consentimento para o bucket do portal e compila o portal com `PORTAL_ASSET_PREFIX=/authorize-static` para que as duas árvores de ativos Next.js não colidam.

## 3. Perfis de Implantação

| | Standalone | Sobreposição |
| :--- | :--- | :--- |
| Público | toda replicação | implantações com site existente |
| Backend padrão | bucket do portal | bucket do site existente |
| Regras de caminho | `/mcp*`, `/api/oauth*`, `/.well-known*` para o Cloud Run | mais os quatro prefixos de consentimento para o bucket do portal |
| `PORTAL_ASSET_PREFIX` | vazio | `/authorize-static` |
| URL pública de consentimento | `/<locale>/authorize/` | idêntica |

## 4. Alternativas Consideradas

### 4.1 Subdomínio para o portal
Isolamento de ativos limpo sem prefixo, mas adiciona registro DNS, entrada de certificado, domínio autorizado no Firebase, referrer da API key e duas variáveis de ambiente no Cloud Run. Rejeitado: mais passos de replicação sem ganho funcional.

### 4.2 Segundo bucket sem prefixo de ativos
Dois builds Next.js serviriam ativos do mesmo caminho `/_next` em um host, e o load balancer roteia um caminho para apenas um backend. Rejeitado: a página de consentimento carregaria o bundle do outro site.

### 4.3 Servir a exportação estática pelo Cloud Run
Remove bucket e CDN, mas reverte o ADR 007, adiciona Node ao build da imagem do backend e coloca o consentimento atrás de um cold start. Rejeitado.

### 4.4 Migrar o site inteiro
Um único build e um único bucket sem prefixo, mas o site de marketing não é necessário para provisionar ou operar o servidor MCP. Adiado; a landing page está fora de escopo.

### 4.5 Manter o repositório externo
Status quo. Rejeitado: este repositório continua incompleto para replicação e o bucket compartilhado segue como risco de correção.

## 5. Consequências
*   O `jor-mcp` é autossuficiente para provisionar o servidor MCP: um bucket, uma exportação estática, um workflow de implantação.
*   Nenhuma mudança de código Python, contrato de API, schema do Firestore ou IAM no backend.
*   O portal tem workflow de implantação manual próprio (`cd-portal.yml`), desacoplado do release da imagem do backend.
*   Valores `NEXT_PUBLIC_*` são embutidos no build, então um build com valores errados ainda compila. O workflow lê esses valores de variáveis do repositório.
*   O site de marketing não é reproduzível a partir deste repositório, e a documentação viva deixa de sugerir que seja.
*   O `service.yaml` passa a definir `OAUTH_SERVER_BASE_URL`, `OAUTH_PORTAL_BASE_URL` e `CORS_ALLOWED_ORIGINS` a partir de `${DOMAIN}`. Antes, uma implantação replicada herdava o domínio de referência nos metadados de descoberta.

## 6. Independência
O perfil standalone não tem dependência de build, implantação, código ou documentação em relação a qualquer repositório externo. O perfil de sobreposição é descrito genericamente como "um site existente no mesmo host"; não nomeia, não linka e não instrui ninguém a criar outro repositório.

Documentos históricos em `docs/*/3-history-and-specs/` mantêm as referências originais. Eles registram o que era verdade na época e não são reescritos.

## 7. Migração e Reversão
Novas implantações seguem os passos standalone e nunca criam um segundo site.

Implantações existentes que servem outro site aplicam o apêndice de sobreposição: criar o bucket do portal, adicionar as regras de caminho, definir `PORTAL_ASSET_PREFIX` e implantar. A reversão remove as quatro regras de caminho; a cópia de consentimento do site anterior volta a ficar acessível.
