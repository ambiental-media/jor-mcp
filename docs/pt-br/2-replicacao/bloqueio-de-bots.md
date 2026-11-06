<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Bloqueio de Bots (Opcional)

> **Orientação opcional.** O Jor-MCP funciona independentemente de o site público da redação bloquear ou não rastreadores. Bloquear crawlers de IA é uma decisão editorial e de negócio, não um requisito de implantação. Esta página explica as peças envolvidas e aponta fontes autoritativas; não é um passo a passo e não é orientação jurídica.

## 1. Dois caminhos de acesso diferentes

| Caminho | Iniciado por | Alcança |
| :--- | :--- | :--- |
| Rastreamento do site público | Mecanismos de busca, crawlers de IA, scrapers | As páginas HTML do site da redação |
| Acesso MCP autorizado | `jor-mcp` no Cloud Run | A API REST do WordPress (`/wp-json/...`) |

A política de crawlers governa a superfície HTML pública. O Jor-MCP lê conteúdo no servidor pela API REST, então os dois são independentes em princípio.

Não são independentes na prática: uma regra que bloqueia todos os user agents que não são navegador, todas as faixas de IP de datacenter ou todo tráfego fora de um país também bloqueia o servidor MCP. Qualquer política precisa manter o caminho de saída do MCP acessível. Veja as referências de egress do Cloud Run abaixo.

## 2. Camadas de controle

Cada camada tem um modelo de aplicação diferente.

**`robots.txt`** — um sinal voluntário definido pelo RFC 9309. Crawlers que o respeitam o seguem; outros podem ignorá-lo. É uma declaração de preferência, não controle de acesso. Uma regra de CDN ou WAF sobrepõe-se nos dois sentidos: um `Allow` no `robots.txt` não contorna um bloqueio de firewall.

**Controles de bots em CDN e WAF** — aplicados na borda, antes de a requisição chegar ao WordPress. Fornecedores modelam tráfego de IA em categorias como treinamento, busca e agente, e cada categoria pode ser permitida ou bloqueada separadamente. Definições e padrões de categoria variam por fornecedor e mudam com o tempo.

**Regras de aplicação e plugins** — aplicadas pelo WordPress ou por um plugin de segurança. É o último recurso: é o lugar mais fácil de quebrar integrações legítimas, incluindo clientes REST que não se parecem com um navegador.

## 3. Fatores de decisão

Não há recomendação padrão aqui. Os trade-offs variam por redação:

- **Finalidade do acesso.** Treinamento, recuperação para busca de IA e acesso de agentes são usos diferentes; uma política pode separá-los.
- **Licenciamento e modelo de negócio.** Bloquear o rastreamento público não impede acesso autorizado e licenciado via Jor-MCP.
- **Visibilidade em busca.** Bloqueios voltados a crawlers de IA também podem afetar indexação se aplicados de forma ampla demais.
- **Dependências operacionais.** Monitoramento, feeds, ferramentas de SEO e o próprio servidor MCP consomem o site como clientes que não são navegador.
- **Custo de manutenção.** Listas de user agent e faixas de IP mudam; categorias gerenciadas pelo fornecedor e padrões publicados envelhecem melhor que regras escritas à mão.

## 4. Referências

| Tópico | Fontes |
| :--- | :--- |
| Padrão de exclusão para robôs | [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) · [Google: introdução ao robots.txt](https://developers.google.com/search/docs/crawling-indexing/robots/intro) · [Google: especificação do robots.txt](https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt) |
| Controles de crawlers de IA, documentação dos fornecedores | [OpenAI bots](https://platform.openai.com/docs/bots) · [Artigo da Anthropic sobre crawlers](https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) · [Crawlers do Google e Google-Extended](https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers) · [Common Crawl CCBot](https://commoncrawl.org/ccbot) · [Apple Applebot-Extended](https://support.apple.com/en-us/119829) |
| Sinais de preferência em desenvolvimento | [Grupo de trabalho IETF AI Preferences (aipref)](https://datatracker.ietf.org/wg/aipref/about/) |
| Controles de bot em CDN e WAF | [Cloudflare bot solutions](https://developers.cloudflare.com/bots/) · [Cloudflare AI bot policies](https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/) · [Cloudflare managed robots.txt](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/) · [AWS WAF Bot Control](https://docs.aws.amazon.com/waf/latest/developerguide/aws-waf-bot-control.html) |
| Camada de aplicação | [Manual da API REST do WordPress](https://developer.wordpress.org/rest-api/) · A documentação do plugin de segurança ou de gestão de bots que o site já utiliza |
| Manter o MCP acessível | [IP de saída estático do Cloud Run](https://cloud.google.com/run/docs/configuring/static-outbound-ip) · [Serverless VPC Access](https://cloud.google.com/vpc/docs/serverless-vpc-access) · [Visão geral do Cloud NAT](https://cloud.google.com/nat/docs/overview) |

A documentação dos fornecedores é a fonte autoritativa para nomes atuais de user agent, categorias e padrões. Isso muda; esta página deliberadamente não os reproduz.

## 5. Documentação relacionada

- [Integração WordPress](../1-tecnico/integracoes/wordpress.md) — como o Jor-MCP lê conteúdo pela API REST.
- [Guia de implantação](guia-de-implantacao.md) — variáveis de ambiente e configuração de runtime.
