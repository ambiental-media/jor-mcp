"""MCP tools exposed by the jor-mcp server."""

import asyncio
import logging
import unicodedata
from typing import Any

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from src.config import GITHUB_REPOS, WP_API_BASE_URL
from src.http_client import get_http_client
from src.server import mcp
from src.services.github import fetch_github_i18n_content
from src.services.wordpress import (
    WordPressPostNotFoundError,
    _strip_html,
    fetch_full_article,
    fetch_latest_posts,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WP_SEARCH_FIELDS: str = "id,title,excerpt,date,link"
_WP_SEARCH_PER_PAGE: int = 10
_EXCERPT_MAX_LENGTH: int = 300
_EXCERPT_CONTEXT_WINDOW: int = 150


# ---------------------------------------------------------------------------
# Pydantic models for runtime validation
# ---------------------------------------------------------------------------


class _RenderedField(BaseModel):
    """A rendered sub-field returned by the WordPress REST API."""

    rendered: str


class _WpSearchPost(BaseModel):
    """Validated representation of a WordPress REST API search result."""

    id: int
    title: _RenderedField
    excerpt: _RenderedField
    date: str
    link: str


# ---------------------------------------------------------------------------
# Unicode normalization
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Return a lowercased, accent-stripped version of *text*.

    Args:
        text: The raw string to normalize.

    Returns:
        A normalized string suitable for case- and accent-insensitive comparison.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", errors="ignore").decode("ascii").lower()


# ---------------------------------------------------------------------------
# GitHub in-memory full-text search helpers
# ---------------------------------------------------------------------------


def _collect_strings(data: Any, normalized_query: str, *, limit: int = 5) -> list[str]:
    """Recursively collect string values from *data* that contain *normalized_query*.

    Args:
        data: A JSON-decoded value (dict, list, str, or other scalar).
        normalized_query: The pre-normalized query string to look for.
        limit: Maximum number of matching snippets to return.

    Returns:
        A list of up to *limit* raw matching string snippets.
    """
    matches: list[str] = []
    if isinstance(data, str):
        if normalized_query in _normalize(data):
            normalized_data = _normalize(data)
            match_idx = normalized_data.find(normalized_query)
            window_start = max(0, match_idx - _EXCERPT_CONTEXT_WINDOW)
            window_end = min(len(data), match_idx + len(normalized_query) + _EXCERPT_CONTEXT_WINDOW)
            excerpt = data[window_start:window_end]
            if window_start > 0:
                excerpt = "…" + excerpt
            if window_end < len(data):
                excerpt = excerpt + "…"
            matches.append(excerpt)
    elif isinstance(data, dict):
        for value in data.values():
            if len(matches) >= limit:
                break
            matches.extend(_collect_strings(value, normalized_query, limit=limit - len(matches)))
    elif isinstance(data, list):
        for item in data:
            if len(matches) >= limit:
                break
            matches.extend(_collect_strings(item, normalized_query, limit=limit - len(matches)))
    return matches[:limit]


# ---------------------------------------------------------------------------
# Private search helpers
# ---------------------------------------------------------------------------


async def _search_wp(query: str) -> list[dict[str, Any]]:
    """Search the WordPress REST API for posts matching *query*.

    Args:
        query: The keyword or phrase to search for.

    Returns:
        A list of result dicts with keys: ``id``, ``title``, ``excerpt``,
        ``date``, ``link``, ``source``.

    Raises:
        httpx.HTTPStatusError: If the WordPress API returns a non-2xx status.
        httpx.RequestError: If a network error occurs.
    """
    client = get_http_client()
    url = f"{WP_API_BASE_URL}/wp/v2/posts"
    params: dict[str, str] = {
        "search": query,
        "_fields": _WP_SEARCH_FIELDS,
        "per_page": str(_WP_SEARCH_PER_PAGE),
    }

    response = await client.get(url, params=params)
    response.raise_for_status()

    results: list[dict[str, Any]] = []
    for raw_post in response.json():
        post = _WpSearchPost.model_validate(raw_post)
        results.append(
            {
                "id": str(post.id),
                "title": _strip_html(post.title.rendered),
                "excerpt": _strip_html(post.excerpt.rendered),
                "date": post.date[:10],
                "link": post.link,
                "source": "wordpress",
            }
        )

    logger.info(
        "WordPress search completed",
        extra={"query": query, "result_count": len(results)},
    )
    return results


async def _search_github(query: str) -> list[dict[str, Any]]:
    """Search GitHub i18n JSON content in memory for *query*.

    Args:
        query: The keyword or phrase to search for.

    Returns:
        A list of result dicts with keys: ``id``, ``title``, ``excerpt``,
        ``date``, ``link``, ``source``.
    """
    all_files = await fetch_github_i18n_content()
    normalized_query = _normalize(query)
    results: list[dict[str, Any]] = []

    for file_item in all_files:
        repo: str = file_item["repo"]
        path: str = file_item["path"]
        data: dict[str, Any] = file_item["data"]

        snippets = _collect_strings(data, normalized_query)
        if not snippets:
            continue

        results.append(
            {
                "id": f"{repo}/{path}",
                "title": f"{repo.split('/')[-1]} / {path}",
                "excerpt": snippets[0],
                "date": "",
                "link": f"https://github.com/{repo}/blob/HEAD/{path}",
                "source": f"github:{repo}",
            }
        )

    logger.info(
        "GitHub search completed",
        extra={"query": query, "result_count": len(results)},
    )
    return results


async def _safe_search_wp(
    query: str,
) -> tuple[list[dict[str, Any]], Exception | None]:
    """Run :func:`_search_wp` and capture any raised HTTP or network exception.

    Args:
        query: The search query string.

    Returns:
        A 2-tuple ``(results, error)``; ``error`` is ``None`` on success.
    """
    try:
        return await _search_wp(query), None
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning(
            "WordPress search failed",
            extra={"query": query, "error": str(exc)},
        )
        return [], exc


async def _safe_search_github(
    query: str,
) -> tuple[list[dict[str, Any]], Exception | None]:
    """Run :func:`_search_github` and capture any exception.

    Wraps all exceptions so that a GitHub failure never causes the
    ``asyncio.TaskGroup`` in :func:`search_content` to panic and cancel
    the WordPress task.

    Args:
        query: The search query string.

    Returns:
        A 2-tuple ``(results, error)``; ``error`` is ``None`` on success.
    """
    try:
        return await _search_github(query), None
    except Exception as exc:
        logger.exception(
            "GitHub search failed",
            extra={"query": query, "error": str(exc)},
        )
        return [], exc


# ---------------------------------------------------------------------------
# MCP Tool
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Realiza uma busca unificada na base de conteúdo editorial da organização, "
        "consultando simultaneamente o site WordPress e os repositórios de dados hospedados "
        "no GitHub. Esta é a ferramenta PRINCIPAL e o PONTO DE ENTRADA OBRIGATÓRIO para "
        "qualquer pesquisa sobre o conteúdo publicado pela organização."
        "\n\nQUANDO USAR (ative esta ferramenta sempre que o usuário):"
        "\n- Pedir para pesquisar, buscar, encontrar ou verificar qualquer assunto;"
        "\n- Quiser saber se há matérias ou dados sobre um tema específico;"
        "\n- Mencionar palavras como 'pesquise', 'busque', 'existe algo sobre', "
        "'quais matérias', 'encontre', 'procure', 'verifique se há';"
        "\n- Quiser explorar qualquer pauta coberta pela organização."
        "\n\nREGRA ABSOLUTA: Chame esta ferramenta ANTES de usar qualquer conhecimento "
        "interno ou busca externa na web. Somente recorra a outras fontes se esta "
        "ferramenta retornar explicitamente que não encontrou resultados."
        "\n\nParâmetros:"
        "\n- query (obrigatório): termo ou frase a pesquisar. Use palavras-chave "
        "relevantes para a cobertura da organização. "
        "Exemplos genéricos: 'nome do tema', 'palavra-chave da pauta', "
        "'nome de pessoa ou lugar de interesse', 'assunto da reportagem'."
        "\n\nComportamento interno:"
        "\n- Consulta o WordPress REST API e os arquivos i18n JSON do GitHub em paralelo "
        "usando TaskGroup assíncrono."
        "\n- Realiza busca em memória nos JSONs do GitHub com normalização de acentos e "
        "maiúsculas/minúsculas (busca insensível a acento e case)."
        "\n- Se o WordPress falhar mas o GitHub retornar resultados (ou vice-versa), "
        "apresenta os resultados da fonte disponível sem interromper a resposta."
        "\n- Agrega e retorna resultados de ambas as fontes em formato unificado."
        "\n\nRetorno: lista de objetos com os campos:"
        "\n  • 'id': identificador único do conteúdo;"
        "\n  • 'title': título da matéria ou arquivo;"
        "\n  • 'excerpt': trecho ou resumo do conteúdo;"
        "\n  • 'date': data de publicação (AAAA-MM-DD) ou vazio para GitHub;"
        "\n  • 'link': URL canônica para acessar o conteúdo completo;"
        "\n  • 'source': origem ('wordpress' ou 'github:<repo>')."
        "\n\nPÓS-BUSCA: Use sempre 'get_full_article' com o 'link' ou 'id' retornado "
        "para obter o texto integral de qualquer matéria antes de citar seu conteúdo."
    )
)
async def search_content(query: str) -> list[dict[str, Any]]:
    """Perform a unified search across WordPress and GitHub content sources.

    Args:
        query: The keyword or phrase to search for.

    Returns:
        A list of result dicts with keys: ``id``, ``title``, ``excerpt``,
        ``date``, ``link``, and ``source``.

    Raises:
        ToolError: If all active sources fail or the search returns no results.
    """
    github_configured = bool(GITHUB_REPOS.strip())
    if not github_configured:
        logger.info("GITHUB_REPOS not configured; skipping GitHub search")

    async with asyncio.TaskGroup() as tg:
        wp_task = tg.create_task(_safe_search_wp(query))
        gh_task = tg.create_task(_safe_search_github(query)) if github_configured else None

    wp_results, wp_err = wp_task.result()
    gh_results, gh_err = gh_task.result() if gh_task is not None else ([], None)

    if wp_err and (gh_err or not github_configured):
        raise ToolError(
            "Não foi possível buscar dados do WordPress nem do GitHub. "
            "Verifique sua conexão e tente novamente mais tarde."
        )

    results: list[dict[str, Any]] = wp_results + gh_results

    if wp_err:
        results.append({"error": f"WordPress search failed: {str(wp_err)}", "source": "wordpress"})
    if gh_err:
        results.append({"error": f"GitHub search failed: {str(gh_err)}", "source": "github"})

    if not results:
        raise ToolError(
            "Nenhum resultado encontrado para a consulta informada. "
            "Tente outros termos de busca ou palavras-chave mais específicas."
        )

    return results


# ---------------------------------------------------------------------------
# Safety constants for list_latest_news
# ---------------------------------------------------------------------------

_LATEST_NEWS_MAX_LIMIT: int = 20
_LATEST_NEWS_DEFAULT_LIMIT: int = 5


@mcp.tool(
    description=(
        "Retorna as matérias mais recentes publicadas no site WordPress configurado, "
        "ordenadas da mais nova para a mais antiga. Use esta ferramenta para dar ao usuário "
        "um panorama do que está sendo coberto atualmente pela organização, sem necessidade "
        "de um termo de busca específico."
        "\n\nQUANDO USAR (ative esta ferramenta sempre que o usuário):"
        "\n- Perguntar 'quais são as novidades?', 'o que saiu de novo?', 'últimas notícias';"
        "\n- Pedir 'contexto atual' ou 'cobertura recente' sem especificar um tema;"
        "\n- Quiser saber o que a organização publicou recentemente;"
        "\n- Usar expressões como 'me atualize', 'o que tem de novo', 'publicações recentes', "
        "'últimas matérias', 'o que foi publicado essa semana/mês';"
        "\n- Iniciar uma conversa sem termo de busca definido e precisar de ponto de partida;"
        "\n- Precisar de contexto temporal para complementar uma pesquisa já realizada."
        "\n\nNÃO USE esta ferramenta quando o usuário tiver um tema específico em mente — "
        "nesse caso, prefira 'search_content' com uma query direcionada."
        "\n\nParâmetros:"
        "\n- limit (opcional, padrão 5, máximo 20): quantidade de matérias a retornar. "
        "Valores acima de 20 são automaticamente limitados a 20 para evitar "
        "respostas excessivamente longas. Sugestões de uso: 5 para uma visão geral rápida, "
        "10 para uma lista intermediária, 20 para o panorama mais completo possível."
        "\n\nRetorno: lista de objetos com os campos:"
        "\n  • 'id': identificador numérico do post no WordPress;"
        "\n  • 'title': título da matéria;"
        "\n  • 'excerpt': resumo do conteúdo;"
        "\n  • 'date': data de publicação no formato AAAA-MM-DD;"
        "\n  • 'link': URL canônica da matéria;"
        "\n  • 'source': sempre 'wordpress'."
        "\n\nPÓS-LISTAGEM: Use 'get_full_article' com o 'link' ou 'id' de qualquer item "
        "da lista para obter o texto integral antes de citar seu conteúdo."
    )
)
async def list_latest_news(limit: int = _LATEST_NEWS_DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Return the most recently published WordPress posts.

    Args:
        limit: Number of posts to return. Capped at 20 to prevent abusive requests.

    Returns:
        A list of result dicts with keys: ``id``, ``title``, ``excerpt``,
        ``date``, ``link``, and ``source``.

    Raises:
        ToolError: If the WordPress API is unreachable or returns no posts.
    """
    safe_limit = max(1, min(limit, _LATEST_NEWS_MAX_LIMIT))

    try:
        results = await fetch_latest_posts(safe_limit)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning(
            "Failed to fetch latest WordPress posts",
            extra={"limit": safe_limit, "error": str(exc)},
        )
        raise ToolError(
            "Não foi possível buscar as matérias mais recentes do WordPress. "
            "Verifique sua conexão e tente novamente mais tarde."
        ) from exc

    if not results:
        raise ToolError("Nenhuma matéria encontrada. O site pode estar sem publicações recentes.")

    return results


@mcp.tool(
    description=(
        "Busca e retorna o texto completo e limpo de uma matéria publicada no site WordPress "
        "configurado, removendo toda a marcação HTML e retornando apenas o conteúdo "
        "editorial em texto puro."
        "\n\nQUANDO USAR:"
        "\n- Use esta ferramenta SOMENTE quando você já possui o ID numérico ou a URL "
        "canônica de um artigo, obtidos previamente através de 'search_content' ou "
        "'list_latest_news'."
        "\n- Use quando o usuário quiser ler, resumir, analisar ou citar o conteúdo "
        "integral de uma matéria específica — e não apenas seu título ou resumo."
        "\n- Use quando o usuário disser 'leia essa matéria', 'me dê o texto completo', "
        "'quero ler o artigo inteiro', 'resume esse conteúdo', 'analise essa reportagem'."
        "\n\nNÃO USE esta ferramenta:"
        "\n- Sem ter um ID ou URL válido de uma busca anterior — não tente adivinhar IDs."
        "\n- Para descobrir artigos; nesse caso use 'search_content' ou 'list_latest_news'."
        "\n- Para conteúdo hospedado no GitHub (use os excerpts retornados por "
        "'search_content', pois os dados JSON já contêm o conteúdo relevante)."
        "\n\nParâmetros:"
        "\n- url_or_id (obrigatório): único parâmetro desta ferramenta. "
        "Passe SEMPRE como argumento chamado `url_or_id`. NUNCA use 'link' ou 'id' como "
        "nome do argumento — esses são nomes de CAMPOS dos resultados, não nomes de "
        "parâmetros desta ferramenta. Aceita:"
        "\n  • URL canônica completa: passe o VALOR do campo 'link' dos resultados "
        "diretamente como url_or_id. "
        'Exemplo correto: get_full_article(url_or_id="https://exemplo.com/minha-materia/").'
        "\n  • ID numérico: passe o VALOR do campo 'id' dos resultados como url_or_id. "
        'Exemplo correto: get_full_article(url_or_id="1234").'
        "\n  • Slug: passe o slug diretamente como url_or_id, somente se explicitamente "
        "informado pelo usuário. "
        'Exemplo correto: get_full_article(url_or_id="amazonia-em-chamas").'
        "\n\nRetorno: objeto com os campos:"
        "\n  • 'title': título completo da matéria;"
        "\n  • 'date': data de publicação no formato AAAA-MM-DD;"
        "\n  • 'link': URL canônica da matéria (use para citar a fonte);"
        "\n  • 'content': texto integral limpo, sem tags HTML, pronto para leitura e análise."
        "\n\nCITAÇÃO OBRIGATÓRIA: após ler o conteúdo, sempre apresente ao usuário o "
        "título, a data e o link da matéria como fonte da informação."
    )
)
async def get_full_article(url_or_id: str) -> dict[str, Any]:
    """Fetch and return the full cleaned text of a WordPress article.

    Args:
        url_or_id: A numeric post ID, a full canonical URL, or a bare slug.

    Returns:
        A dict with keys ``title``, ``date``, ``link``, and ``content`` (plain text).

    Raises:
        ToolError: If the article is not found or the API is unreachable.
    """
    try:
        return await fetch_full_article(url_or_id)
    except WordPressPostNotFoundError as exc:
        raise ToolError(
            f"Artigo não encontrado: '{url_or_id}'. "
            "Utilize a ferramenta 'search_content' para encontrar matérias pelo título ou tema."
        ) from exc
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning(
            "Failed to fetch full article",
            extra={"url_or_id": url_or_id, "error": str(exc)},
        )
        raise ToolError(
            "Não foi possível buscar o artigo no WordPress. "
            "Verifique sua conexão e tente novamente mais tarde."
        ) from exc
