"""Tests for src.services.wordpress."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.wordpress import (
    WordPressPost,
    WordPressPostNotFoundError,
    _extract_slug,
    _fetch_post_by_id,
    _fetch_post_by_slug,
    _strip_html,
    fetch_full_article,
    fetch_latest_posts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_POST: dict[str, object] = {
    "id": 42,
    "title": {"rendered": "Amazônia em Chamas"},
    "date": "2024-08-01T12:00:00",
    "link": "https://ambiental.media/amazonia-em-chamas/",
    "content": {"rendered": "<p>Conteúdo do artigo.</p>"},
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
def mock_client() -> Generator[AsyncMock, None, None]:
    """Inject a mock AsyncClient, bypassing the lifespan initialisation."""
    client = AsyncMock(spec=httpx.AsyncClient)
    with patch("src.services.wordpress.get_http_client", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_removes_paragraph_tags(self) -> None:
        html = "<p>Hello world.</p>"
        assert _strip_html(html) == "Hello world."

    def test_removes_script_blocks(self) -> None:
        html = "<p>Keep this.</p><script>alert('xss');</script>"
        result = _strip_html(html)
        assert "alert" not in result
        assert "Keep this." in result

    def test_removes_style_blocks(self) -> None:
        html = "<style>.foo { color: red; }</style><p>Text.</p>"
        result = _strip_html(html)
        assert ".foo" not in result
        assert "Text." in result

    def test_removes_shortcodes(self) -> None:
        html = "<p>Intro.</p>[gallery ids='1,2,3']<p>Outro.</p>"
        result = _strip_html(html)
        assert "[gallery" not in result
        assert "Intro." in result
        assert "Outro." in result

    def test_removes_closing_shortcodes(self) -> None:
        html = "[caption id='1']<img src='x.jpg'/>[/caption]<p>Text.</p>"
        result = _strip_html(html)
        assert "[caption" not in result
        assert "[/caption]" not in result
        assert "Text." in result

    def test_decodes_html_entities(self) -> None:
        html = "<p>R&eacute;sum&eacute; &amp; notes &mdash; done.</p>"
        result = _strip_html(html)
        assert "&amp;" not in result
        assert "&eacute;" not in result
        assert "Résumé" in result

    def test_collapses_excessive_blank_lines(self) -> None:
        html = "<p>First.</p>\n\n\n\n\n<p>Second.</p>"
        result = _strip_html(html)
        assert "\n\n\n" not in result

    def test_complex_dirty_payload(self) -> None:
        """Simulate a realistic 'dirty' WordPress content block."""
        html = """
        <style>h2 { font-weight: bold; }</style>
        <p>O desmatamento na Amazônia atingiu <strong>recordes históricos</strong>.</p>
        [caption id="attachment_99" align="aligncenter" width="800"]
        <img src="foto.jpg" />[/caption]
        <p>Pesquisadores apontam que &ldquo;a situação é crítica&rdquo;.</p>
        <script>
            window._paq = window._paq || [];
            window._paq.push(['trackPageView']);
        </script>
        [gallery link="file" ids="10,11,12"]
        <p>Fim do relatório.</p>
        """
        result = _strip_html(html)
        assert "<" not in result
        assert ">" not in result
        assert "[gallery" not in result
        assert "[caption" not in result
        assert "trackPageView" not in result
        assert "font-weight" not in result
        assert "desmatamento" in result
        assert "Fim do relatório." in result

    def test_empty_string_returns_empty(self) -> None:
        assert _strip_html("") == ""

    def test_plain_text_passthrough(self) -> None:
        text = "Just plain text, no markup."
        assert _strip_html(text) == text


# ---------------------------------------------------------------------------
# _extract_slug
# ---------------------------------------------------------------------------


class TestExtractSlug:
    @pytest.mark.parametrize(
        "identifier, expected_value, expected_is_id",
        [
            ("123", "123", True),
            ("99999", "99999", True),
            (
                "https://ambiental.media/amazonia-em-chamas/",
                "amazonia-em-chamas",
                False,
            ),
            (
                "https://ambiental.media/categoria/amazonia-em-chamas",
                "amazonia-em-chamas",
                False,
            ),
            (
                "http://ambiental.media/minha-materia/",
                "minha-materia",
                False,
            ),
            ("minha-materia", "minha-materia", False),
            ("amazonia_relatorio", "amazonia_relatorio", False),
        ],
    )
    def test_extraction(self, identifier: str, expected_value: str, expected_is_id: bool) -> None:
        value, is_id = _extract_slug(identifier)
        assert value == expected_value
        assert is_id == expected_is_id

    def test_strips_whitespace(self) -> None:
        value, is_id = _extract_slug("  456  ")
        assert value == "456"
        assert is_id is True

    def test_url_with_no_path_returns_full_url(self) -> None:
        # A URL with only a root path "/" has no meaningful segments.
        value, is_id = _extract_slug("https://ambiental.media/")
        # urlparse path "/" → no segments → fallback to the original stripped URL
        assert is_id is False


# ---------------------------------------------------------------------------
# _fetch_post_by_id
# ---------------------------------------------------------------------------


class TestFetchPostById:
    async def test_success(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, _BASE_POST)

        post = await _fetch_post_by_id(42)

        assert isinstance(post, WordPressPost)
        assert post.id == 42
        assert post.title.rendered == "Amazônia em Chamas"
        mock_client.get.assert_awaited_once()
        call_kwargs = mock_client.get.call_args
        assert "_fields" in call_kwargs.kwargs["params"]

    async def test_404_raises_not_found(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(404)

        with pytest.raises(WordPressPostNotFoundError, match="id=99"):
            await _fetch_post_by_id(99)

    async def test_500_re_raises_http_status_error(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(500)

        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_post_by_id(42)

    async def test_uses_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from src.config import WP_API_BASE_URL

        mock_client.get.return_value = _make_response(200, _BASE_POST)
        await _fetch_post_by_id(7)

        url_called = mock_client.get.call_args.args[0]
        assert url_called == f"{WP_API_BASE_URL}/wp/v2/posts/7"

    async def test_fields_param_is_sent(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, _BASE_POST)
        await _fetch_post_by_id(42)

        params = mock_client.get.call_args.kwargs["params"]
        assert params["_fields"] == "id,title,date,link,content"


# ---------------------------------------------------------------------------
# _fetch_post_by_slug
# ---------------------------------------------------------------------------


class TestFetchPostBySlug:
    async def test_success(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [_BASE_POST])

        post = await _fetch_post_by_slug("amazonia-em-chamas")

        assert isinstance(post, WordPressPost)
        assert post.link == "https://ambiental.media/amazonia-em-chamas/"

    async def test_empty_list_raises_not_found(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [])

        with pytest.raises(WordPressPostNotFoundError, match="slug='nao-existe'"):
            await _fetch_post_by_slug("nao-existe")

    async def test_500_re_raises(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(500)

        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_post_by_slug("qualquer-slug")

    async def test_uses_slug_and_fields_params(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [_BASE_POST])
        await _fetch_post_by_slug("minha-materia")

        params = mock_client.get.call_args.kwargs["params"]
        assert params["slug"] == "minha-materia"
        assert params["_fields"] == "id,title,date,link,content"

    async def test_uses_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from src.config import WP_API_BASE_URL

        mock_client.get.return_value = _make_response(200, [_BASE_POST])
        await _fetch_post_by_slug("minha-materia")

        url_called = mock_client.get.call_args.args[0]
        assert url_called == f"{WP_API_BASE_URL}/wp/v2/posts"


# ---------------------------------------------------------------------------
# fetch_full_article (integration-style, all layers mocked)
# ---------------------------------------------------------------------------


class TestFetchFullArticle:
    _DIRTY_POST = {
        **_BASE_POST,
        "content": {
            "rendered": (
                "<p>Primeiro parágrafo.</p>"
                "[gallery ids='1,2']"
                "<script>evil();</script>"
                "<p>Segundo parágrafo.</p>"
            )
        },
    }

    async def test_by_numeric_id(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, self._DIRTY_POST)

        result = await fetch_full_article("42")

        assert result["title"] == "Amazônia em Chamas"
        assert result["date"] == "2024-08-01T12:00:00"
        assert result["link"] == "https://ambiental.media/amazonia-em-chamas/"
        assert "<" not in result["content"]
        assert "evil" not in result["content"]
        assert "[gallery" not in result["content"]
        assert "Primeiro parágrafo." in result["content"]
        assert "Segundo parágrafo." in result["content"]

    async def test_by_full_url(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [self._DIRTY_POST])

        result = await fetch_full_article("https://ambiental.media/amazonia-em-chamas/")

        # Slug extracted → _fetch_post_by_slug path (returns list)
        assert result["title"] == "Amazônia em Chamas"
        assert "Primeiro parágrafo." in result["content"]

    async def test_by_bare_slug(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [self._DIRTY_POST])

        result = await fetch_full_article("amazonia-em-chamas")

        assert result["title"] == "Amazônia em Chamas"
        assert "<" not in result["content"]

    async def test_not_found_by_id_raises(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(404)

        with pytest.raises(WordPressPostNotFoundError):
            await fetch_full_article("999")

    async def test_not_found_by_slug_raises(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [])

        with pytest.raises(WordPressPostNotFoundError):
            await fetch_full_article("slug-inexistente")

    async def test_returns_cleaned_content_keys(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, _BASE_POST)

        result = await fetch_full_article("42")

        assert set(result.keys()) == {"title", "date", "link", "content"}

    async def test_content_has_no_html_tags(self, mock_client: AsyncMock) -> None:
        heavy_html = {
            **_BASE_POST,
            "content": {
                "rendered": (
                    "<h1>Título</h1>"
                    "<div class='wp-block-group'>"
                    "  <p>Texto <em>importante</em> aqui.</p>"
                    "  <ul><li>Item 1</li><li>Item 2</li></ul>"
                    "</div>"
                    "<style>.hidden{display:none}</style>"
                )
            },
        }
        mock_client.get.return_value = _make_response(200, heavy_html)

        result = await fetch_full_article("42")

        assert "<" not in result["content"]
        assert ">" not in result["content"]
        assert "Texto" in result["content"]
        assert "importante" in result["content"]


# ---------------------------------------------------------------------------
# fetch_latest_posts
# ---------------------------------------------------------------------------

_SAMPLE_WP_SUMMARY_POST: dict[str, object] = {
    "id": 10,
    "title": {"rendered": "Amazônia em Chamas"},
    "excerpt": {"rendered": "<p>Resumo sobre a Amazônia.</p>"},
    "date": "2024-08-01T12:00:00",
    "link": "https://ambiental.media/amazonia-em-chamas/",
}


class TestFetchLatestPosts:
    async def test_returns_formatted_list(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [_SAMPLE_WP_SUMMARY_POST])

        results = await fetch_latest_posts(5)

        assert len(results) == 1
        post = results[0]
        assert post["id"] == "10"
        assert post["title"] == "Amazônia em Chamas"
        assert post["date"] == "2024-08-01"
        assert post["link"] == "https://ambiental.media/amazonia-em-chamas/"
        assert post["source"] == "wordpress"
        assert "<p>" not in post["excerpt"]
        assert "Resumo" in post["excerpt"]

    async def test_result_keys_are_complete(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [_SAMPLE_WP_SUMMARY_POST])

        results = await fetch_latest_posts(1)

        required_keys = {"id", "title", "excerpt", "date", "link", "source"}
        assert required_keys.issubset(results[0].keys())

    async def test_sends_correct_query_params(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [])

        await fetch_latest_posts(7)

        params = mock_client.get.call_args.kwargs["params"]
        assert params["orderby"] == "date"
        assert params["order"] == "desc"
        assert params["per_page"] == "7"
        assert "_fields" in params

    async def test_uses_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from src.config import WP_API_BASE_URL

        mock_client.get.return_value = _make_response(200, [])
        await fetch_latest_posts(5)

        url_called = mock_client.get.call_args.args[0]
        assert url_called == f"{WP_API_BASE_URL}/wp/v2/posts"

    async def test_empty_response_returns_empty_list(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [])

        results = await fetch_latest_posts(5)

        assert results == []

    async def test_multiple_posts_returned(self, mock_client: AsyncMock) -> None:
        second_post = {**_SAMPLE_WP_SUMMARY_POST, "id": 11, "title": {"rendered": "Pantanal"}}
        mock_client.get.return_value = _make_response(200, [_SAMPLE_WP_SUMMARY_POST, second_post])

        results = await fetch_latest_posts(2)

        assert len(results) == 2
        assert results[1]["id"] == "11"
        assert results[1]["title"] == "Pantanal"

    async def test_http_error_raises(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(500)

        with pytest.raises(httpx.HTTPStatusError):
            await fetch_latest_posts(5)

    async def test_date_truncated_to_date_only(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = _make_response(200, [_SAMPLE_WP_SUMMARY_POST])

        results = await fetch_latest_posts(1)

        assert results[0]["date"] == "2024-08-01"
        assert "T" not in results[0]["date"]
