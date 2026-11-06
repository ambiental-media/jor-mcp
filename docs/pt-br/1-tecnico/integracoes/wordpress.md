<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---


# Integração WordPress

*(Placeholder: Como a ferramenta WordPress busca, analisa e limpa dados. Estratégias de limitação de taxa e paginação).*

## Decisão Arquitetural: Por que API REST?
Utilizamos a API REST do WordPress em vez de GraphQL ou conexões diretas de banco de dados para garantir compatibilidade com implantações padrão de redação. Os dados são intensamente limpos (removendo HTML e shortcodes) no lado do servidor porque enviar HTML bruto para um LLM desperdiça tokens da janela de contexto e degrada a qualidade de sumarização do modelo.

## Política de Crawlers e Acesso REST
O bloqueio de bots no site é uma decisão editorial opcional, mas pode afetar esta integração: o servidor MCP acessa o WordPress pela API REST, então regras que bloqueiam IPs de datacenter ou user agents que não são navegador também podem bloquear o MCP. Veja [Bloqueio de Bots](../../2-replicacao/bloqueio-de-bots.md) para os trade-offs e referências autoritativas.