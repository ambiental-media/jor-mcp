# Integração GitHub

*(Placeholder: Como a ferramenta GitHub consulta repositórios, lida com tokens de autenticação e limita escopos de pesquisa).*

## Decisão Arquitetural: Por que Analisar JSON?
Para microsites Next.js hospedados no GitHub, nós analisamos especificamente os arquivos `messages/*.json` pré-renderizados em vez de Markdown bruto ou arquivos React `.tsx`. Isso garante que o LLM receba conteúdo final estruturado sem alucinar sobre a lógica de interface ou variáveis não renderizadas.