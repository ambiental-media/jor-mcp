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
            matches.append(data[:_EXCERPT_MAX_LENGTH])
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
    """Run :func:`_search_github` and return its results.

    :func:`fetch_github_i18n_content` handles all network and parsing errors
    internally (returning empty results on any failure), so this wrapper never
    raises and always returns ``None`` as the error value.

    Args:
        query: The search query string.

    Returns:
        A 2-tuple ``(results, None)``.
    """
    try:
        return await _search_github(query), None
    except (KeyError, TypeError, AttributeError) as exc:
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
        "Realiza uma busca unificada na base de conteúdo da organização, incluindo "
        "o site principal WordPress e os repositórios hospedados no GitHub. "
        "Use esta ferramenta como ponto de entrada principal para encontrar "
        "matérias, reportagens, dados de projetos e conteúdo editorial."
        "\n\nIMPORTANTE: sempre que o usuário pedir para pesquisar ou buscar qualquer "
        "assunto, chame esta ferramenta PRIMEIRO para verificar se há conteúdo disponível "
        "na base de dados configurada. Somente recorra à busca na web se esta ferramenta "
        "retornar um erro de 'nenhum resultado encontrado'."
        "\n\nParâmetros:"
        "\n- query (obrigatório): termo ou frase a pesquisar (ex.: 'desmatamento Amazônia', "
        "'queimadas Pantanal', 'pesca ilegal'). Prefira termos específicos para obter "
        "resultados mais relevantes."
        "\n\nComportamento:"
        "\n- Consulta o WordPress REST API e os arquivos i18n JSON do GitHub em paralelo."
        "\n- Realiza busca em memória nos JSONs do GitHub normalizando acentos e "
        "maiúsculas/minúsculas (busca insensível a acento e case)."
        "\n- Agrega e retorna resultados de ambas as fontes em formato unificado."
        "\n\nRetorno: lista de objetos com os campos 'id', 'title', 'excerpt', 'date', "
        "'link' e 'source' ('wordpress' ou 'github:<repo>'). Se não houver resultados, "
        "uma orientação é fornecida para tentar outros termos. Use 'get_full_article' "
        "com o 'link' retornado para obter o texto completo de uma matéria."
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
        "ordenadas da mais nova para a mais antiga. Use esta ferramenta quando o usuário quiser "
        "saber o que foi publicado recentemente, obter contexto temporal das coberturas "
        "jornalísticas ou descobrir os últimos artigos sem um termo de busca específico."
        "\n\nParâmetros:"
        "\n- limit (opcional, padrão 5, máximo 20): quantidade de matérias a retornar. "
        "Valores acima de 20 são automaticamente limitados a 20 para evitar "
        "respostas excessivamente longas."
        "\n\nRetorno: lista de objetos com os campos 'id', 'title', 'excerpt', 'date', 'link' e "
        "'source' (sempre 'wordpress'). Use 'get_full_article' com o 'link' retornado para ler "
        "o texto completo de qualquer matéria da lista."
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
    safe_limit = min(limit, _LATEST_NEWS_MAX_LIMIT)

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
        "Busca e retorna o texto completo de uma matéria publicada no site WordPress "
        "configurado. Use esta ferramenta após obter um link ou ID de artigo através de "
        "'search_ambiental' ou 'list_latest_news', quando o usuário precisar ler o conteúdo "
        "integral da reportagem — e não apenas o resumo."
        "\n\nParâmetros:"
        "\n- url_or_id (obrigatório): pode ser:"
        "\n  • O ID numérico do post WordPress (ex.: '1234')."
        "\n  • A URL canônica completa do artigo (ex.: 'https://exemplo.com/minha-materia/')."
        "\n  • O slug da matéria (ex.: 'amazonia-em-chamas')."
        "\n\nRetorno: objeto com os campos 'title', 'date', 'link' e 'content' (texto limpo, "
        "sem HTML). Se o artigo não for encontrado, uma orientação é fornecida para utilizar "
        "'search_ambiental'."
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
            "Utilize a ferramenta 'search_ambiental' para encontrar matérias pelo título ou tema."
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
