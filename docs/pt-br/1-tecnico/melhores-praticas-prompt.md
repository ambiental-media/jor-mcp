<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Melhores Práticas de Prompt

Este documento fornece diretrizes e exemplos de prompts para garantir que assistentes de IA (como o Claude) façam um uso ideal, eficiente e econômico das ferramentas do servidor Jor-MCP.

---

## 1. Princípios Fundamentais para Assistentes de IA

Quando um usuário fizer uma pergunta sobre o jornalismo, as matérias ou os conjuntos de dados da Ambiental Media:
1.  **Buscar Primeiro:** Sempre execute uma consulta unificada via `search_content` antes de tentar responder com base em conhecimento prévio ou buscas externas na web.
2.  **Ler o Texto Completo:** Não dependa de resumos curtos ou trechos de busca se precisar resumir ou citar uma matéria. Busque o texto puro, completo e limpo de qualquer artigo correspondente via `get_full_article` usando o URL canônico ou o ID do post.
3.  **Fornecer Citações Precisas:** Após ler e responder, sempre inclua o título exato do artigo, a data de publicação e o link canônico como fonte da informação.

---

## 2. Padrões de Prompt Recomendados (Bons vs. Ruins)

Abaixo estão exemplos de como interagir com o assistente de IA para acionar as ferramentas corretas do Jor-MCP:

### Cenário A: Pesquisando um Tema ou Assunto

*   ❌ **Prompt Ruim:** *"O que a Ambiental Media publicou sobre o Pantanal?"*
    *(Embora funcione, isso pode fazer com que a IA resuma com base apenas nos trechos curtos retornados pela ferramenta de busca).*
*   ✔️ **Prompt Bom:** *"Pesquise por 'Pantanal' usando `search_content`. Depois, por favor, busque o texto completo dos 2 artigos mais relevantes usando `get_full_article` para que possamos fazer um resumo abrangente."*

### Cenário B: Obtendo Contexto Editorial Recente

*   ❌ **Prompt Ruim:** *"Me diga o que há de novo no site."*
    *(Um pouco geral demais e pode resultar na IA pedindo esclarecimentos).*
*   ✔️ **Prompt Bom:** *"Quais são as últimas 5 matérias publicadas pela Ambiental Media? Use `list_latest_news` e me dê um breve resumo de cada uma com seus respectivos links."*

### Cenário C: Aprofundando-se em uma Matéria

*   ❌ **Prompt Ruim:** *"Vi o artigo de ID 1255 na lista. Resume ele para mim com base no trecho da busca."*
    *(Os trechos de busca têm apenas cerca de 300 caracteres e perdem detalhes críticos).*
*   ✔️ **Prompt Bom:** *"Recupere o texto completo do artigo de ID 1255 usando `get_full_article`. Depois de buscado, escreva um resumo de 3 parágrafos detalhando as principais descobertas e a metodologia, e cite o link canônico."*

---

## 3. Exemplo de Prompt de Sistema para o Cliente

Se você estiver configurando um agente personalizado ou um prompt de sistema em uma plataforma como o Claude Enterprise ou um Custom GPT, você pode anexar as seguintes instruções para garantir o comportamento correto do modelo:

```text
Você tem acesso ao servidor Jor-MCP, que expõe ferramentas para consultar a base de dados de jornalismo da Ambiental Media (WordPress e GitHub).

DIRETRIZES ESTRITAS:
1. Para qualquer pergunta sobre a cobertura, investigações ou conjuntos de dados da Ambiental Media, você DEVE chamar 'search_content' primeiro.
2. Assim que os resultados da pesquisa forem retornados, nunca alucine ou assuma conteúdos. Se precisar resumir ou citar um artigo, você DEVE chamar 'get_full_article' com o 'id' ou 'link' correspondente.
3. Sempre cite suas fontes anexando o título exato, a data e o link canônico dos artigos usados ao final de sua resposta.
```
