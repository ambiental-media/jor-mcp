import asyncio
import json
import re
from base64 import b64decode
from html import unescape

import httpx

from fastmcp.exceptions import ToolError

from src.app import mcp
from src.config import GITHUB_REPOS, GITHUB_TOKEN, WORDPRESS_API_URL


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=10,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


@mcp.tool(
    description=(
        "Busca unificada de conteúdo jornalístico da Ambiental Media. "
        "Pesquisa artigos no WordPress e nos microsites Next.js hospedados no GitHub. "
        "Retorna título, resumo, data, ID e link de cada resultado, indicando a fonte."
    )
)
async def search_ambiental(query: str) -> str:
    client = _get_client()

    async def _search_wp() -> list[dict]:
        results = []
        try:
            wp_resp = await client.get(
                f"{WORDPRESS_API_URL}/posts",
                params={
                    "search": query,
                    "per_page": 10,
                    "_fields": "id,title,excerpt,date,link",
                },
            )
            wp_resp.raise_for_status()
            for post in wp_resp.json():
                results.append(
                    {
                        "title": _strip_html(post["title"]["rendered"]),
                        "summary": _strip_html(post["excerpt"]["rendered"]),
                        "date": post["date"][:10],
                        "link": post["link"],
                        "id": post["id"],
                        "source": "wordpress",
                    }
                )
        except httpx.HTTPError:
            results.append(
                {"source": "wordpress", "error": "Não foi possível acessar o WordPress."}
            )
        return results

    async def _search_gh(repo: str) -> list[dict]:
        results = []
        query_lower = query.lower()

        import unicodedata

        def normalize(text):
            if not isinstance(text, str):
                return ""
            return unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII").lower()

        def search_json(obj, query_norm, path=None):
            matches = []
            if path is None:
                path = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    matches += search_json(v, query_norm, path + [str(k)])
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    matches += search_json(item, query_norm, path + [str(idx)])
            elif isinstance(obj, str):
                if query_norm in normalize(obj):
                    matches.append(("/".join(path), obj))
            return matches

        try:
            # 1. Buscar o SHA da branch default
            repo_resp = await client.get(
                f"https://api.github.com/repos/{repo}",
                headers=_github_headers(),
            )
            repo_resp.raise_for_status()
            default_branch = repo_resp.json()["default_branch"]

            # 2. Buscar o SHA da árvore da branch default
            branch_resp = await client.get(
                f"https://api.github.com/repos/{repo}/git/trees/{default_branch}?recursive=1",
                headers=_github_headers(),
            )
            branch_resp.raise_for_status()
            tree = branch_resp.json()["tree"]

            # 3. Filtrar arquivos pt.json e en.json
            json_files = [
                f["path"]
                for f in tree
                if f["type"] == "blob" and (f["path"].endswith("pt.json") or f["path"].endswith("en.json"))
            ]

            # 4. Buscar e processar cada arquivo
            async def _fetch_json_file(path: str) -> None:
                try:
                    gh_resp = await client.get(
                        f"https://api.github.com/repos/{repo}/contents/{path}",
                        headers=_github_headers(),
                    )
                    gh_resp.raise_for_status()
                    content = b64decode(gh_resp.json()["content"]).decode()
                    messages = json.loads(content)
                    query_norm = normalize(query)
                    matches = search_json(messages, query_norm)
                    for match_path, match_val in matches:
                        results.append(
                            {
                                "title": match_path,
                                "summary": match_val[:200],
                                "date": None,
                                "link": f"https://github.com/{repo}/blob/{default_branch}/{path}",
                                "source": f"github:{repo}:{path}",
                            }
                        )
                except Exception as e:
                    results.append(
                        {
                            "source": f"github:{repo}:{path}",
                            "error": f"Erro ao acessar {path} em {repo}: {e}",
                        }
                    )

            await asyncio.gather(*[_fetch_json_file(p) for p in json_files])
        except Exception as e:
            results.append(
                {
                    "source": f"github:{repo}",
                    "error": f"Erro ao buscar arquivos JSON no repositório: {e}",
                }
            )
        return results

    tasks = [_search_wp()] + [_search_gh(repo) for repo in GITHUB_REPOS]
    all_results = await asyncio.gather(*tasks)
    results = [item for sublist in all_results for item in sublist]

    if not results:
        raise ToolError(
            f"Nenhum resultado encontrado para '{query}'. "
            "Tente termos mais amplos ou verifique a ortografia."
        )

    lines = [f'Resultados da busca por "{query}":\n']
    for i, r in enumerate(results, 1):
        if "error" in r:
            lines.append(f"{i}. [ERRO] Fonte: {r['source']} — {r['error']}")
        else:
            lines.append(f"{i}. **{r['title']}**")
            lines.append(f"   Resumo: {r['summary']}")
            if r.get("date"):
                lines.append(f"   Data: {r['date']}")
            if r.get("id"):
                lines.append(f"   ID: {r['id']}")
            lines.append(f"   Link: {r['link']}")
            lines.append(f"   Fonte: {r['source']}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "Recupera o conteúdo completo de um artigo da Ambiental Media. "
        "Aceita a URL completa do artigo ou o ID numérico do WordPress. "
        "Retorna o texto limpo e formatado para leitura por LLM. "
        "Use a URL ou o ID retornado por search_ambiental ou list_latest_news."
    )
)
async def get_full_article(url_or_id: str) -> str:
    client = _get_client()

    article_id: int | None = None
    slug: str | None = None

    if url_or_id.isdigit():
        article_id = int(url_or_id)
    else:
        slug = url_or_id.rstrip("/").rsplit("/", 1)[-1]

    try:
        if article_id is not None:
            resp = await client.get(
                f"{WORDPRESS_API_URL}/posts/{article_id}",
                params={"_fields": "id,title,content,date,link"},
            )
        else:
            resp = await client.get(
                f"{WORDPRESS_API_URL}/posts",
                params={"slug": slug, "_fields": "id,title,content,date,link"},
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ToolError(
                f"Artigo '{url_or_id}' não encontrado. "
                "Tente buscar por palavra-chave usando search_ambiental."
            )
        raise ToolError(
            f"Erro ao acessar o artigo: HTTP {e.response.status_code}"
        )
    except httpx.HTTPError:
        raise ToolError("Erro de conexão ao acessar o WordPress.")

    data = resp.json()
    if isinstance(data, list):
        if not data:
            raise ToolError(
                f"Artigo '{url_or_id}' não encontrado. "
                "Tente buscar por palavra-chave usando search_ambiental."
            )
        post = data[0]
    else:
        post = data

    title = _strip_html(post["title"]["rendered"])
    content = _strip_html(post["content"]["rendered"])
    date = post["date"][:10]
    link = post["link"]

    return (
        f"# {title}\n\n"
        f"**Publicado em:** {date}\n"
        f"**Link:** {link}\n\n"
        f"---\n\n"
        f"{content}"
    )


@mcp.tool(
    description=(
        "Lista as últimas notícias publicadas pela Ambiental Media. "
        "Útil para dar contexto temporal recente ao agente. "
        "O parâmetro limit define quantas notícias retornar (padrão: 5, máximo: 20)."
    )
)
async def list_latest_news(limit: int = 5) -> str:
    limit = max(1, min(limit, 20))
    client = _get_client()

    try:
        resp = await client.get(
            f"{WORDPRESS_API_URL}/posts",
            params={
                "per_page": limit,
                "orderby": "date",
                "order": "desc",
                "_fields": "id,title,excerpt,date,link",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        raise ToolError(
            "Erro ao acessar o WordPress. Tente novamente em instantes."
        )

    posts = resp.json()
    if not posts:
        return "Nenhuma notícia encontrada."

    lines = [f"Últimas {len(posts)} notícias da Ambiental Media:\n"]
    for i, post in enumerate(posts, 1):
        title = _strip_html(post["title"]["rendered"])
        excerpt = _strip_html(post["excerpt"]["rendered"])
        date = post["date"][:10]
        lines.append(f"{i}. **{title}** ({date})")
        lines.append(f"   Resumo: {excerpt}")
        lines.append(f"   ID: {post['id']}")
        lines.append(f"   Link: {post['link']}")
        lines.append("")

    return "\n".join(lines)
