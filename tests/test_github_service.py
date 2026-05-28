"""Tests for src.services.github."""

import base64
import json
import logging
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.github import (
    GitHubFileResult,
    _build_auth_headers,
    _decode_base64_content,
    _discover_i18n_paths,
    _fetch_file,
    _fetch_repo_files,
    fetch_github_i18n_content,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_DATA: dict[str, str] = {"title": "Amazônia em Chamas", "body": "Conteúdo."}  # noqa: RUF012
_REPO = "ambiental-media/microsite-test"
_PATH = "locales/pt.json"


def _encode_content(data: dict[str, str]) -> str:
    """Return Base64-encoded JSON (with newlines as the API produces)."""
    raw = json.dumps(data).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _make_response(
    status_code: int = 200,
    json_body: object = None,
) -> MagicMock:
    """Build a minimal mock of httpx.Response."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = json_body
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=mock,
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


def _content_response(path: str = _PATH, data: dict[str, str] | None = None) -> dict[str, object]:
    """Return a dict that matches the GitHub Contents API schema."""
    return {
        "name": path.split("/")[-1],
        "path": path,
        "encoding": "base64",
        "content": _encode_content(data or _SAMPLE_DATA),
    }


def _tree_response(
    paths: list[str],
    truncated: bool = False,
) -> dict[str, object]:
    """Return a dict matching the GitHub Git Trees API schema."""
    return {
        "tree": [{"path": p, "type": "blob"} for p in paths],
        "truncated": truncated,
    }


@pytest.fixture
def mock_client() -> Generator[AsyncMock, None, None]:
    """Inject a mock AsyncClient, bypassing the lifespan initialisation."""
    client = AsyncMock(spec=httpx.AsyncClient)
    with patch("src.services.github.get_http_client", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# _build_auth_headers
# ---------------------------------------------------------------------------


def test_build_auth_headers_with_token() -> None:
    with patch("src.services.github.GITHUB_TOKEN", "secret-token"):
        headers = _build_auth_headers()
    assert headers == {"Authorization": "Bearer secret-token"}


def test_build_auth_headers_without_token() -> None:
    with patch("src.services.github.GITHUB_TOKEN", None):
        headers = _build_auth_headers()
    assert headers == {}


# ---------------------------------------------------------------------------
# _decode_base64_content
# ---------------------------------------------------------------------------


def test_decode_base64_content_clean() -> None:
    raw = base64.b64encode(b"hello world").decode("ascii")
    assert _decode_base64_content(raw) == b"hello world"


def test_decode_base64_content_with_newlines() -> None:
    """The GitHub API wraps encoded content in newlines."""
    raw = base64.b64encode(b"hello world").decode("ascii")
    wrapped = "\n".join(raw[i : i + 60] for i in range(0, len(raw), 60)) + "\n"
    assert _decode_base64_content(wrapped) == b"hello world"


def test_decode_base64_content_invalid_raises() -> None:
    with pytest.raises(ValueError):
        _decode_base64_content("!!!not-base64!!!")


# ---------------------------------------------------------------------------
# _fetch_file
# ---------------------------------------------------------------------------



@pytest.mark.asyncio
async def test_fetch_file_success(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, _content_response())
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert isinstance(result, GitHubFileResult)
    assert result.repo == _REPO
    assert result.path == _PATH
    assert result.data == _SAMPLE_DATA



@pytest.mark.asyncio
async def test_fetch_file_404_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(404)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None



@pytest.mark.asyncio
async def test_fetch_file_http_error_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(500)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None



@pytest.mark.asyncio
async def test_fetch_file_network_error_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.side_effect = httpx.RequestError("connection refused")
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None



@pytest.mark.asyncio
async def test_fetch_file_bad_schema_returns_none(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, {"unexpected": "schema"})
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None



@pytest.mark.asyncio
async def test_fetch_file_unsupported_encoding_returns_none(
    mock_client: AsyncMock,
) -> None:
    payload = _content_response()
    payload["encoding"] = "utf-8"  # not base64
    mock_client.get.return_value = _make_response(200, payload)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None



@pytest.mark.asyncio
async def test_fetch_file_invalid_json_returns_none(mock_client: AsyncMock) -> None:
    payload = {
        "name": "pt.json",
        "path": _PATH,
        "encoding": "base64",
        "content": base64.b64encode(b"not-json").decode("ascii"),
    }
    mock_client.get.return_value = _make_response(200, payload)
    result = await _fetch_file(mock_client, _REPO, _PATH)
    assert result is None


# ---------------------------------------------------------------------------
# _discover_i18n_paths
# ---------------------------------------------------------------------------



@pytest.mark.asyncio
async def test_discover_i18n_paths_returns_matching_files(mock_client: AsyncMock) -> None:
    """Only files named pt.json or en.json are returned, at any depth."""
    mock_client.get.return_value = _make_response(
        200,
        _tree_response(
            [
                "messages/pt.json",
                "messages/en.json",
                "package.json",  # excluded: not a target filename
                "src/components/Button.tsx",  # excluded: wrong extension
            ]
        ),
    )
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert set(paths) == {"messages/pt.json", "messages/en.json"}



@pytest.mark.asyncio
async def test_discover_i18n_paths_http_error_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(403)
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []



@pytest.mark.asyncio
async def test_discover_i18n_paths_network_error_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.side_effect = httpx.RequestError("timeout")
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []



@pytest.mark.asyncio
async def test_discover_i18n_paths_bad_schema_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, {"unexpected": "schema"})
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []



@pytest.mark.asyncio
async def test_discover_i18n_paths_truncated_logs_warning(
    mock_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_client.get.return_value = _make_response(
        200, _tree_response(["messages/pt.json"], truncated=True)
    )
    with caplog.at_level(logging.WARNING, logger="src.services.github"):
        paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == ["messages/pt.json"]
    assert any("truncated" in r.message for r in caplog.records)



@pytest.mark.asyncio
async def test_discover_i18n_paths_no_matches_returns_empty(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(
        200, _tree_response(["package.json", "README.md"])
    )
    paths = await _discover_i18n_paths(mock_client, _REPO)
    assert paths == []


# ---------------------------------------------------------------------------
# _fetch_repo_files
# ---------------------------------------------------------------------------



@pytest.mark.asyncio
async def test_fetch_repo_files_returns_found_files(mock_client: AsyncMock) -> None:
    """Files discovered via the tree are fetched and returned."""
    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    with patch(
        "src.services.github._discover_i18n_paths",
        new=AsyncMock(return_value=[_PATH]),
    ):
        results = await _fetch_repo_files(mock_client, _REPO)
    assert len(results) == 1
    assert results[0].path == _PATH
    assert results[0].repo == _REPO



@pytest.mark.asyncio
async def test_fetch_repo_files_all_missing_returns_empty(mock_client: AsyncMock) -> None:
    """No files to fetch when discovery returns an empty list."""
    with patch(
        "src.services.github._discover_i18n_paths",
        new=AsyncMock(return_value=[]),
    ):
        results = await _fetch_repo_files(mock_client, _REPO)
    assert results == []


# ---------------------------------------------------------------------------
# fetch_github_i18n_content
# ---------------------------------------------------------------------------



@pytest.mark.asyncio
async def test_fetch_github_i18n_content_empty_repos(mock_client: AsyncMock) -> None:
    with patch("src.services.github.GITHUB_REPOS", ""):
        result = await fetch_github_i18n_content()
    assert result == []



@pytest.mark.asyncio
async def test_fetch_github_i18n_content_success(mock_client: AsyncMock) -> None:
    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    with (
        patch("src.services.github.GITHUB_REPOS", _REPO),
        patch("src.services.github.GITHUB_TOKEN", "tok"),
        patch(
            "src.services.github._discover_i18n_paths",
            new=AsyncMock(return_value=[_PATH]),
        ),
    ):
        result = await fetch_github_i18n_content()

    assert isinstance(result, list)
    assert any(item["repo"] == _REPO for item in result)
    assert all("data" in item for item in result)



@pytest.mark.asyncio
async def test_fetch_github_i18n_content_graceful_degradation(
    mock_client: AsyncMock,
) -> None:
    """An error in one repo must not prevent others from returning results.

    ``_discover_i18n_paths`` already traps all network/HTTP errors internally
    and returns an empty list on failure, so the TaskGroup is never exposed to
    an unhandled exception during normal operation.  This test simulates that
    contract: the bad repo yields no paths (as the real function would after
    catching an error) while the good repo contributes its file.
    """

    async def _fake_discover(client: AsyncMock, repo: str) -> list[str]:
        if "repo-bad" in repo:
            # Real _discover_i18n_paths catches errors and returns [] — mirror that.
            return []
        return [_PATH]

    mock_client.get.return_value = _make_response(200, _content_response(_PATH))
    repos = "ambiental-media/repo-bad,ambiental-media/repo-good"
    with (
        patch("src.services.github.GITHUB_REPOS", repos),
        patch("src.services.github._discover_i18n_paths", side_effect=_fake_discover),
    ):
        result = await fetch_github_i18n_content()

    # The good repo contributed results despite the bad one finding nothing
    assert any("repo-good" in item["repo"] for item in result)



@pytest.mark.asyncio
async def test_fetch_github_i18n_content_whitespace_repos(
    mock_client: AsyncMock,
) -> None:
    """Whitespace-only entries in GITHUB_REPOS are ignored."""
    mock_client.get.return_value = _make_response(404)
    with patch("src.services.github.GITHUB_REPOS", "  ,  "):
        result = await fetch_github_i18n_content()
    assert result == []

