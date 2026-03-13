import asyncio
import json
import re
from base64 import b64decode
from html import unescape

import httpx

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
        try:
            gh_resp = await client.get(
                f"https://api.github.com/repos/{repo}/contents/messages/pt.json",
                headers=_github_headers(),
            )
            gh_resp.raise_for_status()
            content = b64decode(gh_resp.json()["content"]).decode()
            messages = json.loads(content)

            query_lower = query.lower()
            for key, value in messages.items():
                if isinstance(value, str) and query_lower in value.lower():
                    results.append(
                        {
                            "title": key,
                            "summary": value[:200],
                            "date": None,
                            "link": f"https://github.com/{repo}",
                            "source": f"github:{repo}",
                        }
                    )
        except httpx.HTTPError:
            results.append(
                {
                    "source": f"github:{repo}",
                    "error": f"Não foi possível acessar o repositório {repo}.",
                }
            )
        return results

    tasks = [_search_wp()] + [_search_gh(repo) for repo in GITHUB_REPOS]
    all_results = await asyncio.gather(*tasks)
    results = [item for sublist in all_results for item in sublist]

    if not results:
        raise ValueError(
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
        "Recupera o conteúdo completo de um artigo da Ambiental Media pelo ID do WordPress. "
        "Retorna o texto limpo e formatado para leitura por LLM. "
        "Use o ID retornado por search_ambiental ou list_latest_news."
    )
)
async def get_full_article(article_id: int) -> str:
    client = _get_client()
    try:
        resp = await client.get(
                f"{WORDPRESS_API_URL}/posts/{article_id}",
                params={"_fields": "id,title,content,date,link"},
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError(
                f"Artigo com ID {article_id} não encontrado. "
                "Tente buscar por palavra-chave usando search_ambiental."
            )
        raise ValueError(
            f"Erro ao acessar o artigo: HTTP {e.response.status_code}"
        )
    except httpx.HTTPError:
        raise ValueError("Erro de conexão ao acessar o WordPress.")

    post = resp.json()
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
        raise ValueError(
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
