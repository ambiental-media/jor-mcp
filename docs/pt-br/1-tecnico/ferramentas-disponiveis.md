<img src="/assets/ambiental-logo.png" alt="Logo Ambiental Media" style="float:right; vertical-align:middle" height="50em"><img src="/assets/jor-logo.png" alt="Logo Jor-MCP" style="float:left; vertical-align:middle" height="50em">

---

# Referência de Ferramentas Disponíveis

Este documento fornece uma referência detalhada das ferramentas do Model Context Protocol (MCP) expostas pelo servidor Jor-MCP. Essas ferramentas permitem que clientes de LLM consultem e recuperem conteúdo editorial e jornalístico do site WordPress da Ambiental Media e de repositórios de dados no GitHub.

---

## 1. Busca Unificada (`search_content`)

Esta é a **ferramenta principal** e o ponto de entrada obrigatório para qualquer pesquisa geral ou consulta de usuário sobre conteúdo publicado.

### Descrição
Realiza uma busca concorrente e unificada na API REST do WordPress e nos arquivos JSON editoriais multilíngues hospedados no GitHub.
- **Insensibilidade a Acentos e Caixa:** A normalização da busca remove acentos e ignora letras maiúsculas/minúsculas (por exemplo, buscar "amazonia" corresponde a "Amazônia").
- **Falha Graciosa:** Se o WordPress falhar mas o GitHub retornar resultados (ou vice-versa), apresenta os resultados da fonte disponível sem interromper a resposta.

### Parâmetros
*   `query` (`string`, obrigatório): O termo de busca, palavra-chave, tema, local ou frase a pesquisar.

### Retorno (`list[dict[str, Any]]`)
Retorna um array JSON de itens correspondentes. Cada item segue o seguinte esquema:
- `id` (`string`): Identificador único do recurso (por exemplo, ID do post no WordPress ou `repo/path` para arquivos do GitHub).
- `title` (`string`): O título limpo (sem tags HTML) do post ou nome do arquivo.
- `excerpt` (`string`): Um trecho do texto contendo a janela contextual do termo buscado.
- `date` (`string`): Data de publicação (`AAAA-MM-DD`) ou vazio se for do GitHub.
- `link` (`string`): URL canônica para acessar o conteúdo completo.
- `source` (`string`): Origem da correspondência (`"wordpress"` ou `"github:<repo>"`).
- `error` (`string`, opcional): Presente apenas se um dos backends falhou durante a consulta.

---

## 2. Listar Notícias Recentes (`list_latest_news`)

Use esta ferramenta quando o usuário solicitar atualizações gerais, novas publicações ou um panorama geral da cobertura atual, sem um termo de busca específico em mente.

### Descrição
Recupera uma lista das matérias publicadas mais recentemente no site WordPress, ordenadas de forma cronológica decrescente.
- **Prevenção de Abuso:** O limite de resultados é estritamente limitado a `20` itens para evitar payloads de tokens excessivamente grandes.

### Parâmetros
| Nome | Tipo | Padrão | Descrição | Obrigatório |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | `integer` | `5` | Número de matérias recentes a recuperar (limitado entre `1` e `20`). | Não |

### Retorno (`list[dict[str, Any]]`)
Retorna um array de resumos de matérias correspondentes:
- `id` (`string`): ID numérico do post no WordPress.
- `title` (`string`): O título limpo.
- `excerpt` (`string`): Texto de resumo/trecho da matéria.
- `date` (`string`): Data de publicação (`AAAA-MM-DD`).
- `link` (`string`): URL canônica da matéria.
- `source` (`string`): Sempre `"wordpress"`.

---

## 3. Buscar Artigo Completo (`get_full_article`)

Use esta ferramenta **apenas** após obter um URL, ID ou slug válido de uma busca anterior ou lista de novidades. Não tente adivinhar IDs.

### Descrição
Busca um post específico na API REST do WordPress e extrai o conteúdo completo do corpo, removendo toda a marcação HTML para retornar um texto puro, limpo e editorial, otimizado para leitura, resumo e citação por LLMs.

### Parâmetros
*   `url_or_id` (`string`, obrigatório): Um ID de post numérico (ex: `"123"`), um URL canônico completo (ex: `"https://ambiental.media/desmatamento-na-amazonia/"`) ou um slug de post.

### Retorno (`dict[str, Any]`)
Retorna um único objeto com o texto completo e limpo:
- `title` (`string`): Título limpo da matéria.
- `date` (`string`): Data de publicação (`AAAA-MM-DD`).
- `link` (`string`): URL canônica (para citação de fonte).
- `content` (`string`): Texto completo limpo do artigo, sem tags HTML.
