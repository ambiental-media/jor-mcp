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
from src.services.wordpress import _strip_html

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
    """Run :func:`_search_github` and capture any raised exception.

    Args:
        query: The search query string.

    Returns:
        A 2-tuple ``(results, error)``; ``error`` is ``None`` on success.
    """
    try:
        return await _search_github(query), None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "GitHub search failed",
            extra={"query": query, "error": str(exc)},
        )
        return [], exc


# ---------------------------------------------------------------------------
# MCP Tool
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Realiza uma busca unificada em todo o ecossistema Ambiental Media, incluindo "
        "o site principal WordPress (ambiental.media) e os microsites Next.js hospedados "
        "no GitHub. Use esta ferramenta como ponto de entrada principal para encontrar "
        "matérias, reportagens, dados de projetos e conteúdo editorial."
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
async def search_ambiental(query: str) -> list[dict[str, Any]]:
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
