"""WordPress REST API service layer.

Provides async functions for fetching and cleaning article content from the
WordPress REST API.  All HTML tags, shortcodes, and layout artefacts are
stripped before the text is returned to the caller, making it safe to pass
directly to an LLM without risking token-budget overruns or hallucinations
caused by markup noise.
"""

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from src.config import WP_API_BASE_URL
from src.http_client import get_http_client

logger = logging.getLogger(__name__)

# Fields requested from WordPress to keep the payload small.
_WP_FIELDS: str = "id,title,date,link,content"

# Matches WordPress shortcodes: [tag attr="val"] and [/tag]
_SHORTCODE_RE: re.Pattern[str] = re.compile(r"\[/?[a-zA-Z_\-]+[^\]]*\]")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WordPressPostNotFoundError(Exception):
    """Raised when a requested WordPress post does not exist (HTTP 404)."""


# ---------------------------------------------------------------------------
# Pydantic models for runtime validation
# ---------------------------------------------------------------------------


class _RenderedField(BaseModel):
    """A rendered sub-field returned by the WordPress REST API.

    Fields such as ``title`` and ``content`` nest their actual value under a
    ``rendered`` key.
    """

    rendered: str


class WordPressPost(BaseModel):
    """Validated representation of a WordPress REST API post object."""

    id: int
    title: _RenderedField
    date: str
    link: str
    content: _RenderedField


class _WpLatestPost(BaseModel):
    """Validated representation of a WordPress post summary used for latest-news listings."""

    id: int
    title: _RenderedField
    excerpt: _RenderedField
    date: str
    link: str


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------


def _strip_html(html: str) -> str:
    """Remove all HTML markup and return clean plain text.

    The cleaning pipeline:

    1. Removes ``<script>`` and ``<style>`` blocks (with their inner content).
    2. Parses the remaining HTML with BeautifulSoup using the built-in
       ``html.parser`` engine (no extra system dependency required).
    3. Extracts the visible text, using a newline as the block separator.
    4. Strips WordPress shortcode patterns (``[gallery …]``, ``[caption …]``).
    5. Collapses three or more consecutive newlines into a single blank line.

    Args:
        html: Raw HTML string sourced from the ``content.rendered`` field of a
            WordPress REST API response.

    Returns:
        Plain text with HTML entities decoded and whitespace normalised.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Destroy script/style blocks including their content.
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Remove shortcodes that survive the HTML parsing step.
    text = _SHORTCODE_RE.sub("", text)

    # Collapse excessive blank lines produced by block-level tag separators.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Identifier parsing
# ---------------------------------------------------------------------------


def _extract_slug(url_or_id: str) -> tuple[str, bool]:
    """Parse *url_or_id* and return ``(value, is_numeric_id)``.

    Args:
        url_or_id: Either a numeric post ID (as a string), a full URL
            (``https://ambiental.media/minha-materia/``), or a bare slug
            (``minha-materia``).

    Returns:
        A 2-tuple where the first element is the extracted slug or ID string
        and the second is ``True`` when the value should be interpreted as an
        integer post ID.
    """
    stripped = url_or_id.strip()

    if stripped.isdigit():
        return stripped, True

    if stripped.startswith(("http://", "https://")):
        path = urlparse(stripped).path
        # Pick the last non-empty path segment as the slug.
        segments = [s for s in path.split("/") if s]
        slug = segments[-1] if segments else stripped
        return slug, False

    return stripped, False


# ---------------------------------------------------------------------------
# Private fetch helpers
# ---------------------------------------------------------------------------


async def _fetch_post_by_id(post_id: int) -> WordPressPost:
    """Fetch a single WordPress post by its numeric ID.

    Args:
        post_id: The numeric WordPress post ID.

    Returns:
        A validated ``WordPressPost`` model.

    Raises:
        WordPressPostNotFoundError: If the post returns HTTP 404.
        httpx.HTTPStatusError: For other non-2xx HTTP responses.
    """
    client = get_http_client()
    url = f"{WP_API_BASE_URL}/wp/v2/posts/{post_id}"
    params: dict[str, str] = {"_fields": _WP_FIELDS}

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.warning(
                "WordPress post not found",
                extra={"post_id": post_id, "status_code": 404},
            )
            raise WordPressPostNotFoundError(f"Post with id={post_id} not found") from exc
        raise

    return WordPressPost.model_validate(response.json())


async def _fetch_post_by_slug(slug: str) -> WordPressPost:
    """Fetch a single WordPress post by its URL slug.

    The WordPress REST API returns an array when querying by slug; this
    function returns the first match or raises if the list is empty.

    Args:
        slug: The URL slug of the post (e.g. ``"amazonia-em-chamas"``).

    Returns:
        A validated ``WordPressPost`` model.

    Raises:
        WordPressPostNotFoundError: If no post matches the given slug.
        httpx.HTTPStatusError: For non-2xx HTTP responses.
    """
    client = get_http_client()
    url = f"{WP_API_BASE_URL}/wp/v2/posts"
    params: dict[str, str] = {"slug": slug, "_fields": _WP_FIELDS}

    response = await client.get(url, params=params)
    response.raise_for_status()

    posts: list[Any] = response.json()
    if not posts:
        logger.warning(
            "WordPress post not found by slug",
            extra={"slug": slug},
        )
        raise WordPressPostNotFoundError(f"Post with slug='{slug}' not found")

    return WordPressPost.model_validate(posts[0])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_full_article(identifier: str) -> dict[str, Any]:
    """Fetch and return the cleaned full text of a WordPress article.

    Accepts a numeric post ID, a full article URL, or a bare slug.  The raw
    HTML ``content.rendered`` field is sanitised through ``_strip_html`` before
    being returned so the output is ready for LLM consumption.

    Args:
        identifier: One of:

            * A numeric WordPress post ID (``"1234"``).
            * A full canonical URL
              (``"https://ambiental.media/minha-materia/"``).
            * A bare slug (``"minha-materia"``).

    Returns:
        A dictionary with keys ``title``, ``date``, ``link``, and ``content``
        (plain text, HTML-free).

    Raises:
        WordPressPostNotFoundError: If no matching post is found on WordPress.
        httpx.HTTPStatusError: For unexpected upstream API errors.
    """
    value, is_id = _extract_slug(identifier)

    if is_id:
        post = await _fetch_post_by_id(int(value))
    else:
        post = await _fetch_post_by_slug(value)

    logger.info(
        "WordPress article fetched",
        extra={"post_id": post.id, "link": post.link},
    )

    return {
        "title": post.title.rendered,
        "date": post.date,
        "link": post.link,
        "content": _strip_html(post.content.rendered),
    }


async def fetch_latest_posts(limit: int) -> list[dict[str, Any]]:
    """Fetch the most recently published WordPress posts.

    Args:
        limit: Number of posts to retrieve, ordered by publication date descending.

    Returns:
        A list of dicts with keys ``id``, ``title``, ``excerpt``, ``date``,
        ``link``, and ``source``.

    Raises:
        httpx.HTTPStatusError: If the WordPress API returns a non-2xx status.
        httpx.RequestError: If a network error occurs.
    """
    # Fields requested from WordPress to keep the payload small.
    _fields = "id,title,excerpt,date,link"

    client = get_http_client()
    url = f"{WP_API_BASE_URL}/wp/v2/posts"
    params: dict[str, str] = {
        "orderby": "date",
        "order": "desc",
        "per_page": str(limit),
        "_fields": _fields,
    }

    response = await client.get(url, params=params)
    response.raise_for_status()

    results: list[dict[str, Any]] = []
    for raw_post in response.json():
        post = _WpLatestPost.model_validate(raw_post)
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
        "WordPress latest posts fetched",
        extra={"limit": limit, "result_count": len(results)},
    )
    return results
