"""GitHub Content API service layer.

Fetches i18n JSON files (``pt.json`` / ``en.json``) from multiple GitHub
repositories owned by Ambiental Media and consolidates their content for
use in the unified search tool.

File discovery is performed via the GitHub Git Trees API, which returns the
full recursive tree of the default branch.  Any file named ``pt.json`` or
``en.json`` is fetched, regardless of its depth or directory.  The Contents
API returns file data encoded in Base64; this module handles decoding
defensively and validates the decoded structure through Pydantic before
returning it to the caller.
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from src.config import GITHUB_API_BASE_URL, GITHUB_REPOS, GITHUB_TOKEN
from src.http_client import get_http_client

logger = logging.getLogger(__name__)

# Filenames that identify i18n content, matched against any depth in the tree.
_I18N_FILENAMES: frozenset[str] = frozenset({"pt.json", "en.json"})


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class _GitHubContentResponse(BaseModel):
    """Minimal validated representation of a GitHub Contents API response."""

    name: str
    path: str
    encoding: str
    content: str


class _GitHubTreeItem(BaseModel):
    """A single entry returned by the GitHub Git Trees API."""

    path: str
    type: str  # "blob" (file) or "tree" (directory)


class _GitHubTreeResponse(BaseModel):
    """Minimal validated representation of a GitHub Git Trees API response."""

    tree: list[_GitHubTreeItem]
    truncated: bool


class GitHubFileResult(BaseModel):
    """A successfully decoded i18n file from a GitHub repository."""

    repo: str
    path: str
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_auth_headers() -> dict[str, str]:
    """Return Authorization headers if a token is configured.

    Returns:
        A dict with the ``Authorization`` header when ``GITHUB_TOKEN`` is set,
        otherwise an empty dict.
    """
    if GITHUB_TOKEN:
        return {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    return {}


def _decode_base64_content(raw: str) -> bytes:
    """Decode Base64-encoded content returned by the GitHub Contents API.

    The API concatenates the encoded content across multiple lines separated
    by ``\\n``.  This helper strips whitespace before decoding to handle that
    format defensively.

    Args:
        raw: The raw ``content`` string from the GitHub API response.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the string is not valid Base64.
    """
    return base64.b64decode(raw.replace("\n", "").strip())


async def _fetch_file(
    client: httpx.AsyncClient,
    repo: str,
    path: str,
) -> GitHubFileResult | None:
    """Attempt to fetch and decode a single file from a GitHub repository.

    Args:
        client: The shared async HTTP client.
        repo: Repository identifier in ``owner/repo`` format.
        path: Path to the file inside the repository.

    Returns:
        A ``GitHubFileResult`` when the file exists and decodes successfully,
        or ``None`` if the file does not exist (HTTP 404) or cannot be parsed.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{repo}/contents/{path}"
    try:
        response = await client.get(url, headers=_build_auth_headers())
    except httpx.RequestError as exc:
        logger.warning(
            "Network error fetching GitHub file",
            extra={"repo": repo, "path": path, "error": str(exc)},
        )
        return None

    if response.status_code == 404:
        logger.debug(
            "GitHub file not found",
            extra={"repo": repo, "path": path},
        )
        return None

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "HTTP error fetching GitHub file",
            extra={"repo": repo, "path": path, "status": exc.response.status_code},
        )
        return None

    try:
        payload = _GitHubContentResponse.model_validate(response.json())
    except ValidationError as exc:
        logger.warning(
            "Unexpected GitHub API response schema",
            extra={"repo": repo, "path": path, "error": str(exc)},
        )
        return None

    if payload.encoding != "base64":
        logger.warning(
            "Unsupported GitHub file encoding",
            extra={"repo": repo, "path": path, "encoding": payload.encoding},
        )
        return None

    try:
        raw_bytes = _decode_base64_content(payload.content)
        decoded_str = raw_bytes.decode("utf-8", errors="ignore")
        data: dict[str, Any] = json.loads(decoded_str)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed to decode GitHub file content",
            extra={"repo": repo, "path": path, "error": str(exc)},
        )
        return None

    return GitHubFileResult(repo=repo, path=path, data=data)


async def _discover_i18n_paths(
    client: httpx.AsyncClient,
    repo: str,
) -> list[str]:
    """Discover i18n JSON file paths inside a repository via the Git Trees API.

    Fetches the full recursive tree of the default branch and returns the
    path of every file whose name is ``pt.json`` or ``en.json``, regardless
    of directory depth.

    Args:
        client: The shared async HTTP client.
        repo: Repository identifier in ``owner/repo`` format.

    Returns:
        A list of matching file paths.  Returns an empty list on any error so
        callers can degrade gracefully.
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{repo}/git/trees/HEAD"
    try:
        response = await client.get(
            url,
            headers=_build_auth_headers(),
            params={"recursive": "1"},
        )
    except httpx.RequestError as exc:
        logger.warning(
            "Network error fetching repo tree",
            extra={"repo": repo, "error": str(exc)},
        )
        return []

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "HTTP error fetching repo tree: status=%d body=%s",
            exc.response.status_code,
            exc.response.text[:500],
            extra={"repo": repo, "status": exc.response.status_code},
        )
        return []

    try:
        payload = _GitHubTreeResponse.model_validate(response.json())
    except ValidationError as exc:
        logger.warning(
            "Unexpected tree API response schema",
            extra={"repo": repo, "error": str(exc)},
        )
        return []

    if payload.truncated:
        logger.warning(
            "GitHub tree response was truncated; some i18n files may be missed",
            extra={"repo": repo},
        )

    return [
        item.path
        for item in payload.tree
        if item.type == "blob" and Path(item.path).name in _I18N_FILENAMES
    ]


async def _fetch_repo_files(
    client: httpx.AsyncClient,
    repo: str,
) -> list[GitHubFileResult]:
    """Fetch all i18n JSON files found in a single repository.

    Discovers candidate paths via the Git Trees API (any file named
    ``pt.json`` or ``en.json`` at any depth), then fetches and decodes each
    one via the Contents API.

    Args:
        client: The shared async HTTP client.
        repo: Repository identifier in ``owner/repo`` format.

    Returns:
        A list of ``GitHubFileResult`` objects (may be empty).
    """
    paths = await _discover_i18n_paths(client, repo)
    results: list[GitHubFileResult] = []

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_fetch_file(client, repo, path)) for path in paths]

    for task in tasks:
        if (result := task.result()) is not None:
            results.append(result)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_github_i18n_content() -> list[dict[str, Any]]:
    """Fetch and consolidate i18n JSON content from all configured repositories.

    Reads ``GITHUB_REPOS`` (a comma-separated list of ``owner/repo`` strings),
    then for each repository attempts to retrieve all known i18n JSON file
    candidates via the GitHub Contents API.

    Failures for individual repositories are logged at WARNING level and do
    **not** raise exceptions, allowing the remaining repositories to return
    successfully (graceful degradation).

    Returns:
        A flat list of dicts, each representing one successfully fetched file.
        Keys: ``repo`` (str), ``path`` (str), ``data`` (dict).
        On complete failure (e.g. empty ``GITHUB_REPOS``), returns an empty
        list.
    """
    if not GITHUB_REPOS.strip():
        logger.warning("GITHUB_REPOS is not configured; skipping GitHub ingestion")
        return []

    repos = [r.strip() for r in GITHUB_REPOS.split(",") if r.strip()]
    client = get_http_client()
    consolidated: list[dict[str, Any]] = []

    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_fetch_repo_files(client, repo)) for repo in repos]
    except* Exception as eg:
        logger.exception(
            "Unexpected error fetching GitHub repo content",
            extra={"errors": [str(e) for e in eg.exceptions]},
        )

    for task in tasks:
        if not task.cancelled() and task.exception() is None:
            for file_result in task.result():
                consolidated.append(file_result.model_dump())

    return consolidated
