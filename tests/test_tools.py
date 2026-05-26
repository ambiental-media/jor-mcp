"""Tests for src.tools."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastmcp.exceptions import ToolError

from src.tools import (
    _collect_strings,
    _normalize,
    _safe_search_github,
    _safe_search_wp,
    _search_github,
    _search_wp,
    get_full_article,
    list_latest_news,
    search_content,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_WP_POST: dict[str, object] = {
    "id": 7,
    "title": {"rendered": "Amazônia em Chamas"},
    "excerpt": {"rendered": "<p>Resumo do artigo sobre a Amazônia.</p>"},
    "date": "2024-08-01T12:00:00",
    "link": "https://ambiental.media/amazonia-em-chamas/",
}

_SAMPLE_GITHUB_FILE: dict[str, object] = {
    "repo": "ambiental-media/microsite-amazonia",
    "path": "messages/pt.json",
    "data": {
        "title": "Amazônia em Chamas",
        "body": "O desmatamento na floresta amazônica atingiu recordes históricos.",
        "nested": {"subtitle": "Queimadas no Pantanal afetam biodiversidade"},
    },
}


def _make_response(status_code: int = 200, json_body: object = None) -> MagicMock:
    """Build a mock httpx.Response."""
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


@pytest.fixture
def mock_wp_client() -> Generator[AsyncMock, None, None]:
    """Inject a mock AsyncClient, bypassing the lifespan initialisation."""
    client = AsyncMock(spec=httpx.AsyncClient)
    with patch("src.tools.get_http_client", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_lowercases(self) -> None:
        assert _normalize("AMAZÔNIA") == "amazonia"

    def test_strips_accents(self) -> None:
        assert _normalize("queimadas") == "queimadas"
        assert _normalize("Pantanal") == "pantanal"
        assert _normalize("café") == "cafe"
        assert _normalize("histórico") == "historico"

    def test_combines_both(self) -> None:
        assert _normalize("HISTÓRICO") == "historico"

    def test_empty_string(self) -> None:
        assert _normalize("") == ""

    def test_already_normalized(self) -> None:
        assert _normalize("amazonia") == "amazonia"

    def test_mixed_unicode(self) -> None:
        assert _normalize("ção") == "cao"


# ---------------------------------------------------------------------------
# _collect_strings
# ---------------------------------------------------------------------------


class TestCollectStrings:
    def test_matches_plain_string(self) -> None:
        result = _collect_strings("amazonia em chamas", "amazonia")
        assert result == ["amazonia em chamas"]

    def test_no_match_in_string(self) -> None:
        result = _collect_strings("pantanal", "amazonia")
        assert result == []

    def test_match_in_dict_values(self) -> None:
        data = {"key": "amazonia em chamas", "other": "sem relação"}
        result = _collect_strings(data, "amazonia")
        assert len(result) == 1
        assert "amazonia" in result[0]

    def test_match_in_list_items(self) -> None:
        data = ["pantanal", "amazonia em chamas", "cerrado"]
        result = _collect_strings(data, "amazonia")
        assert len(result) == 1
        assert "amazonia" in result[0]

    def test_match_in_nested_dict(self) -> None:
        data = {"outer": {"inner": "desmatamento na amazonia"}}
        result = _collect_strings(data, "desmatamento")
        assert len(result) == 1

    def test_accent_insensitive_match(self) -> None:
        # Query 'amazonia' should match the accented 'Amazônia'
        result = _collect_strings("Amazônia em Chamas", "amazonia")
        assert len(result) == 1

    def test_respects_limit(self) -> None:
        data = {str(i): f"amazonia item {i}" for i in range(10)}
        result = _collect_strings(data, "amazonia", limit=3)
        assert len(result) <= 3

    def test_trims_long_string_to_excerpt_max(self) -> None:
        long_string = "amazonia " + ("x" * 400)
        result = _collect_strings(long_string, "amazonia")
        assert len(result) == 1
        assert len(result[0]) == 300  # _EXCERPT_MAX_LENGTH

    def test_non_string_scalars_ignored(self) -> None:
        data = {"count": 42, "flag": True, "value": None}
        result = _collect_strings(data, "amazonia")
        assert result == []

    def test_empty_data(self) -> None:
        assert _collect_strings({}, "amazonia") == []
        assert _collect_strings([], "amazonia") == []


# ---------------------------------------------------------------------------
# _search_wp
# ---------------------------------------------------------------------------


class TestSearchWp:
    async def test_success_returns_formatted_results(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.return_value = _make_response(200, [_SAMPLE_WP_POST])

        results = await _search_wp("amazonia")

        assert len(results) == 1
        assert results[0]["id"] == "7"
        assert results[0]["title"] == "Amazônia em Chamas"
        assert results[0]["source"] == "wordpress"
        assert results[0]["link"] == "https://ambiental.media/amazonia-em-chamas/"
        assert results[0]["date"] == "2024-08-01"
        # Excerpt HTML should be stripped
        assert "<p>" not in results[0]["excerpt"]
        assert "Resumo" in results[0]["excerpt"]

    async def test_empty_results_list(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.return_value = _make_response(200, [])

        results = await _search_wp("termo-inexistente")

        assert results == []

    async def test_raises_on_http_error(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.return_value = _make_response(500)

        with pytest.raises(httpx.HTTPStatusError):
            await _search_wp("amazonia")

    async def test_raises_on_request_error(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.side_effect = httpx.RequestError("Connection refused")

        with pytest.raises(httpx.RequestError):
            await _search_wp("amazonia")

    async def test_sends_correct_params(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.return_value = _make_response(200, [])

        await _search_wp("desmatamento")

        call_kwargs = mock_wp_client.get.call_args
        params = call_kwargs.kwargs["params"]
        assert params["search"] == "desmatamento"
        assert "_fields" in params
        assert "per_page" in params

    async def test_multiple_results(self, mock_wp_client: AsyncMock) -> None:
        second_post = {**_SAMPLE_WP_POST, "id": 8, "title": {"rendered": "Pantanal"}}
        mock_wp_client.get.return_value = _make_response(200, [_SAMPLE_WP_POST, second_post])

        results = await _search_wp("amazonia")

        assert len(results) == 2
        assert results[1]["id"] == "8"


# ---------------------------------------------------------------------------
# _search_github
# ---------------------------------------------------------------------------


class TestSearchGithub:
    async def test_returns_matching_file(self) -> None:
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
        ):
            results = await _search_github("amazonia")

        assert len(results) == 1
        result = results[0]
        assert result["source"] == "github:ambiental-media/microsite-amazonia"
        assert "microsite-amazonia" in result["title"]
        assert "messages/pt.json" in result["title"]
        assert "github.com" in result["link"]
        assert result["id"] == "ambiental-media/microsite-amazonia/messages/pt.json"

    async def test_accent_insensitive_match(self) -> None:
        # Query 'historico' (no accent) should match 'históricos' in the data
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
        ):
            results = await _search_github("historico")

        assert len(results) == 1

    async def test_no_match_returns_empty(self) -> None:
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
        ):
            results = await _search_github("termo-que-nao-existe")

        assert results == []

    async def test_empty_files_returns_empty(self) -> None:
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[]),
        ):
            results = await _search_github("amazonia")

        assert results == []

    async def test_multiple_files_multiple_matches(self) -> None:
        second_file = {
            "repo": "ambiental-media/microsite-pantanal",
            "path": "messages/pt.json",
            "data": {"body": "Queimadas no Pantanal"},
        }
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE, second_file]),
        ):
            results = await _search_github("amazonia")

        # Only the first file matches "amazonia"
        assert len(results) == 1
        assert "microsite-amazonia" in results[0]["source"]

    async def test_date_field_is_empty_string(self) -> None:
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
        ):
            results = await _search_github("amazonia")

        assert results[0]["date"] == ""


# ---------------------------------------------------------------------------
# _safe_search_wp
# ---------------------------------------------------------------------------


class TestSafeSearchWp:
    async def test_returns_results_on_success(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.return_value = _make_response(200, [_SAMPLE_WP_POST])

        results, err = await _safe_search_wp("amazonia")

        assert err is None
        assert len(results) == 1

    async def test_captures_http_error(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.return_value = _make_response(500)

        results, err = await _safe_search_wp("amazonia")

        assert results == []
        assert isinstance(err, httpx.HTTPStatusError)

    async def test_captures_request_error(self, mock_wp_client: AsyncMock) -> None:
        mock_wp_client.get.side_effect = httpx.RequestError("timeout")

        results, err = await _safe_search_wp("amazonia")

        assert results == []
        assert isinstance(err, httpx.RequestError)


# ---------------------------------------------------------------------------
# _safe_search_github
# ---------------------------------------------------------------------------


class TestSafeSearchGithub:
    async def test_returns_results_on_success(self) -> None:
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
        ):
            results, err = await _safe_search_github("amazonia")

        assert err is None
        assert len(results) == 1

    async def test_captures_unexpected_exception(self) -> None:
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(side_effect=RuntimeError("unexpected")),
        ):
            results, err = await _safe_search_github("amazonia")

        assert results == []
        assert isinstance(err, RuntimeError)


# ---------------------------------------------------------------------------
# search_content (the MCP tool)
# ---------------------------------------------------------------------------


class TestSearchAmbiental:
    async def test_returns_aggregated_results(self, mock_wp_client: AsyncMock) -> None:
        """Results from both WP and GitHub are merged into a single list."""
        mock_wp_client.get.return_value = _make_response(200, [_SAMPLE_WP_POST])
        with (
            patch("src.tools.GITHUB_REPOS", "ambiental-media/microsite-amazonia"),
            patch(
                "src.tools.fetch_github_i18n_content",
                new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
            ),
        ):
            results = await search_content("amazonia")

        sources = {r["source"] for r in results}
        assert "wordpress" in sources
        assert any(s.startswith("github:") for s in sources)

    async def test_raises_tool_error_when_both_fail(self, mock_wp_client: AsyncMock) -> None:
        """ToolError is raised when both WP and GitHub queries fail."""
        mock_wp_client.get.return_value = _make_response(503)
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            with pytest.raises(ToolError):
                await search_content("amazonia")

    async def test_succeeds_when_only_wp_fails(self, mock_wp_client: AsyncMock) -> None:
        """Partial failure (WP down) still returns GitHub results."""
        mock_wp_client.get.return_value = _make_response(500)
        with (
            patch("src.tools.GITHUB_REPOS", "ambiental-media/microsite-amazonia"),
            patch(
                "src.tools.fetch_github_i18n_content",
                new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
            ),
        ):
            results = await search_content("amazonia")

        assert len(results) >= 1
        assert all(r["source"].startswith("github:") for r in results)

    async def test_succeeds_when_only_github_fails(self, mock_wp_client: AsyncMock) -> None:
        """Partial failure (GitHub down) still returns WP results."""
        mock_wp_client.get.return_value = _make_response(200, [_SAMPLE_WP_POST])
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(side_effect=RuntimeError("gh down")),
        ):
            results = await search_content("amazonia")

        assert len(results) >= 1
        assert all(r["source"] == "wordpress" for r in results)

    async def test_raises_tool_error_on_empty_results(self, mock_wp_client: AsyncMock) -> None:
        """ToolError with guidance is raised when both sources return empty."""
        mock_wp_client.get.return_value = _make_response(200, [])
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[]),
        ):
            with pytest.raises(ToolError, match="Nenhum resultado"):
                await search_content("termo-inexistente")

    async def test_result_fields_are_standardised(self, mock_wp_client: AsyncMock) -> None:
        """Every result dict contains the required keys."""
        mock_wp_client.get.return_value = _make_response(200, [_SAMPLE_WP_POST])
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(return_value=[_SAMPLE_GITHUB_FILE]),
        ):
            results = await search_content("amazonia")

        required_keys = {"id", "title", "excerpt", "date", "link", "source"}
        for result in results:
            assert required_keys.issubset(result.keys()), f"Missing keys in: {result}"

    async def test_tool_error_message_when_both_fail(self, mock_wp_client: AsyncMock) -> None:
        """ToolError message mentions both WordPress and GitHub."""
        mock_wp_client.get.side_effect = httpx.RequestError("timeout")
        with patch(
            "src.tools.fetch_github_i18n_content",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            with pytest.raises(ToolError, match="WordPress"):
                await search_content("amazonia")


# ---------------------------------------------------------------------------
# get_full_article (the MCP tool)
# ---------------------------------------------------------------------------

_SAMPLE_FULL_ARTICLE: dict[str, str] = {
    "title": "Amazônia em Chamas",
    "date": "2024-08-01T12:00:00",
    "link": "https://ambiental.media/amazonia-em-chamas/",
    "content": "Conteúdo completo do artigo sobre a Amazônia.",
}


class TestGetFullArticle:
    async def test_returns_article_by_id(self) -> None:
        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(return_value=_SAMPLE_FULL_ARTICLE),
        ):
            result = await get_full_article("42")

        assert result["title"] == "Amazônia em Chamas"
        assert result["content"] == "Conteúdo completo do artigo sobre a Amazônia."

    async def test_returns_article_by_url(self) -> None:
        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(return_value=_SAMPLE_FULL_ARTICLE),
        ):
            result = await get_full_article("https://ambiental.media/amazonia-em-chamas/")

        assert result["link"] == "https://ambiental.media/amazonia-em-chamas/"

    async def test_returns_article_by_slug(self) -> None:
        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(return_value=_SAMPLE_FULL_ARTICLE),
        ):
            result = await get_full_article("amazonia-em-chamas")

        assert set(result.keys()) == {"title", "date", "link", "content"}

    async def test_not_found_raises_tool_error_with_search_hint(self) -> None:
        from src.services.wordpress import WordPressPostNotFoundError

        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(side_effect=WordPressPostNotFoundError("Post not found")),
        ):
            with pytest.raises(ToolError, match="search_ambiental"):
                await get_full_article("slug-inexistente")

    async def test_not_found_error_mentions_identifier(self) -> None:
        from src.services.wordpress import WordPressPostNotFoundError

        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(side_effect=WordPressPostNotFoundError("Post not found")),
        ):
            with pytest.raises(ToolError, match="slug-inexistente"):
                await get_full_article("slug-inexistente")

    async def test_http_error_raises_tool_error(self) -> None:
        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "HTTP 500", request=MagicMock(), response=MagicMock()
                )
            ),
        ):
            with pytest.raises(ToolError, match="WordPress"):
                await get_full_article("42")

    async def test_request_error_raises_tool_error(self) -> None:
        with patch(
            "src.tools.fetch_full_article",
            new=AsyncMock(side_effect=httpx.RequestError("timeout")),
        ):
            with pytest.raises(ToolError):
                await get_full_article("42")


# ---------------------------------------------------------------------------
# list_latest_news (the MCP tool)
# ---------------------------------------------------------------------------

_SAMPLE_LATEST_POSTS: list[dict[str, str]] = [
    {
        "id": "10",
        "title": "Amazônia em Chamas",
        "excerpt": "Resumo da matéria sobre a Amazônia.",
        "date": "2024-08-01",
        "link": "https://ambiental.media/amazonia-em-chamas/",
        "source": "wordpress",
    },
    {
        "id": "11",
        "title": "Pantanal sob Ameaça",
        "excerpt": "Resumo da matéria sobre o Pantanal.",
        "date": "2024-07-28",
        "link": "https://ambiental.media/pantanal-sob-ameaca/",
        "source": "wordpress",
    },
]


class TestListLatestNews:
    async def test_returns_latest_posts(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=_SAMPLE_LATEST_POSTS),
        ):
            results = await list_latest_news(limit=2)

        assert len(results) == 2
        assert results[0]["title"] == "Amazônia em Chamas"
        assert results[0]["source"] == "wordpress"

    async def test_default_limit_is_five(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=_SAMPLE_LATEST_POSTS),
        ) as mock_fetch:
            await list_latest_news()

        mock_fetch.assert_awaited_once_with(5)

    async def test_limit_capped_at_twenty(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=_SAMPLE_LATEST_POSTS),
        ) as mock_fetch:
            await list_latest_news(limit=1000)

        # Should be capped to 20
        mock_fetch.assert_awaited_once_with(20)

    async def test_result_fields_are_standardised(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=_SAMPLE_LATEST_POSTS),
        ):
            results = await list_latest_news()

        required_keys = {"id", "title", "excerpt", "date", "link", "source"}
        for result in results:
            assert required_keys.issubset(result.keys())

    async def test_http_error_raises_tool_error(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "HTTP 503", request=MagicMock(), response=MagicMock()
                )
            ),
        ):
            with pytest.raises(ToolError, match="WordPress"):
                await list_latest_news()

    async def test_request_error_raises_tool_error(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(side_effect=httpx.RequestError("connection refused")),
        ):
            with pytest.raises(ToolError):
                await list_latest_news()

    async def test_empty_results_raises_tool_error(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=[]),
        ):
            with pytest.raises(ToolError, match="Nenhuma matéria"):
                await list_latest_news()

    async def test_respects_valid_limit(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=_SAMPLE_LATEST_POSTS),
        ) as mock_fetch:
            await list_latest_news(limit=10)

        mock_fetch.assert_awaited_once_with(10)

    async def test_limit_at_boundary_twenty(self) -> None:
        with patch(
            "src.tools.fetch_latest_posts",
            new=AsyncMock(return_value=_SAMPLE_LATEST_POSTS),
        ) as mock_fetch:
            await list_latest_news(limit=20)

        mock_fetch.assert_awaited_once_with(20)
