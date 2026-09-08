"""Unit tests for the Firecrawl-backed course-authoring tools
(src/services/ai/tools/). No network calls — httpx is mocked throughout.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.ai.tools import course_tools, firecrawl


def _patch_ai_config(monkeypatch, **overrides):
    fields = {"firecrawl_url": None, "firecrawl_api_key": None}
    fields.update(overrides)
    cfg = SimpleNamespace(**fields)
    monkeypatch.setattr(
        firecrawl, "get_learnhouse_config", lambda: SimpleNamespace(ai_config=cfg)
    )


class TestFirecrawlConfig:
    def test_is_configured_false_when_url_unset(self, monkeypatch):
        _patch_ai_config(monkeypatch)
        assert firecrawl.is_configured() is False

    def test_is_configured_true_when_url_set(self, monkeypatch):
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        assert firecrawl.is_configured() is True

    @pytest.mark.asyncio
    async def test_search_returns_empty_without_network_call_when_unconfigured(self, monkeypatch):
        _patch_ai_config(monkeypatch)
        with patch("httpx.AsyncClient.post") as mock_post:
            result = await firecrawl.search("python basics")
        mock_post.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_scrape_returns_none_without_network_call_when_unconfigured(self, monkeypatch):
        _patch_ai_config(monkeypatch)
        with patch("httpx.AsyncClient.post") as mock_post:
            result = await firecrawl.scrape("https://example.com")
        mock_post.assert_not_called()
        assert result is None


class TestFirecrawlSearch:
    @pytest.mark.asyncio
    async def test_search_happy_path(self, monkeypatch):
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"title": "Intro to Python", "url": "https://example.com/py", "description": "A guide"},
                {"title": "No URL here", "description": "skipped"},
            ]
        }
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await firecrawl.search("python basics", limit=3)

        mock_post.assert_awaited_once_with(
            "/v1/search", json={"query": "python basics", "limit": 3}
        )
        # The result missing a "url" is dropped rather than surfaced as a broken link.
        assert result == [
            {"title": "Intro to Python", "url": "https://example.com/py", "description": "A guide"}
        ]

    @pytest.mark.asyncio
    async def test_search_swallows_network_errors(self, monkeypatch):
        """A flaky/misconfigured self-hosted Firecrawl instance degrades the
        agent (no search results) rather than breaking course generation."""
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await firecrawl.search("python basics")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_sends_bearer_token_when_api_key_set(self, monkeypatch):
        _patch_ai_config(
            monkeypatch, firecrawl_url="http://localhost:3002", firecrawl_api_key="secret-key"
        )
        client = firecrawl._client()
        try:
            assert client.headers["Authorization"] == "Bearer secret-key"
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_no_auth_header_when_api_key_unset(self, monkeypatch):
        """A self-hosted instance run with USE_DB_AUTHENTICATION=false needs no key."""
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        client = firecrawl._client()
        try:
            assert "Authorization" not in client.headers
        finally:
            await client.aclose()


class TestFirecrawlScrape:
    @pytest.mark.asyncio
    async def test_scrape_happy_path(self, monkeypatch):
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"markdown": "# Hello\nWorld"}}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await firecrawl.scrape("https://example.com")
        assert result == "# Hello\nWorld"

    @pytest.mark.asyncio
    async def test_scrape_swallows_network_errors(self, monkeypatch):
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await firecrawl.scrape("https://example.com")
        assert result is None


class TestCourseAuthoringTools:
    def test_no_tools_when_firecrawl_unconfigured(self, monkeypatch):
        _patch_ai_config(monkeypatch)
        assert course_tools.course_authoring_tools() == []

    def test_three_tools_when_firecrawl_configured(self, monkeypatch):
        _patch_ai_config(monkeypatch, firecrawl_url="http://localhost:3002")
        tools = course_tools.course_authoring_tools()
        assert tools == [
            course_tools.search_web,
            course_tools.find_video,
            course_tools.fetch_page_content,
        ]


class TestFindVideo:
    @pytest.mark.asyncio
    async def test_find_video_picks_first_video_host_result(self, monkeypatch):
        async def fake_search(query, limit=5):
            assert query == "recursion video"
            return [
                {"title": "Blog post", "url": "https://example.com/recursion", "description": ""},
                {"title": "Recursion Explained", "url": "https://www.youtube.com/watch?v=abc123", "description": ""},
                {"title": "Another video", "url": "https://vimeo.com/999", "description": ""},
            ]

        monkeypatch.setattr(firecrawl, "search", fake_search)
        result = await course_tools.find_video("recursion")
        assert result == {"title": "Recursion Explained", "url": "https://www.youtube.com/watch?v=abc123"}

    @pytest.mark.asyncio
    async def test_find_video_returns_none_when_no_video_result(self, monkeypatch):
        async def fake_search(query, limit=5):
            return [{"title": "Article", "url": "https://example.com/article", "description": ""}]

        monkeypatch.setattr(firecrawl, "search", fake_search)
        result = await course_tools.find_video("recursion")
        assert result is None

    @pytest.mark.parametrize(
        "raw_url,expected",
        [
            ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            # Non-YouTube hosts (e.g. Vimeo) pass through untouched.
            ("https://vimeo.com/123456", "https://vimeo.com/123456"),
        ],
    )
    def test_normalize_youtube_url(self, raw_url, expected):
        assert course_tools._normalize_youtube_url(raw_url) == expected


class TestFetchPageContent:
    @pytest.mark.asyncio
    async def test_delegates_to_firecrawl_scrape(self, monkeypatch):
        async def fake_scrape(url):
            assert url == "https://example.com/page"
            return "content"

        monkeypatch.setattr(firecrawl, "scrape", fake_scrape)
        result = await course_tools.fetch_page_content("https://example.com/page")
        assert result == "content"
