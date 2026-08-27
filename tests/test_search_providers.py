"""Tests for search engine handler functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sgr_agent_core.models import SourceData


class TestRearrangeSources:
    """Tests for _rearrange_sources helper."""

    def test_renumbers_from_starting_number(self):
        from sgr_agent_core.tools.web_search_tool import _rearrange_sources

        sources = [
            SourceData(number=0, url="https://a.com", title="A", snippet="a"),
            SourceData(number=0, url="https://b.com", title="B", snippet="b"),
        ]
        result = _rearrange_sources(sources, starting_number=5)
        assert result[0].number == 5
        assert result[1].number == 6


class TestBraveSearchHandler:
    """Tests for Brave search handler function."""

    def test_convert_brave_response(self):
        from sgr_agent_core.tools.web_search_tool import _convert_brave_response

        response = {
            "web": {
                "results": [
                    {"title": "Test", "url": "https://example.com", "description": "A test result"},
                    {"title": "Test2", "url": "https://example2.com", "description": "Another result"},
                    {"title": "No URL", "url": "", "description": "Skipped"},
                ]
            }
        }
        sources = _convert_brave_response(response)
        assert len(sources) == 2
        assert sources[0].title == "Test"
        assert sources[0].url == "https://example.com"
        assert sources[0].snippet == "A test result"

    @pytest.mark.asyncio
    async def test_search_calls_brave_api(self):
        from sgr_agent_core.tools.web_search_tool import _search_brave

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result", "url": "https://example.com", "description": "desc"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.tools.web_search_tool.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await _search_brave(
                api_key="test-key",
                api_base_url="https://api.search.brave.com/res/v1/web/search",
                query="test query",
                max_results=5,
                offset=0,
            )

            mock_client.get.assert_called_once()
            call_kwargs = mock_client.get.call_args
            assert call_kwargs.kwargs["params"]["q"] == "test query"
            assert call_kwargs.kwargs["params"]["count"] == 5
            assert len(sources) == 1


class TestPerplexitySearchHandler:
    """Tests for Perplexity search handler function."""

    def test_convert_perplexity_response(self):
        from sgr_agent_core.tools.web_search_tool import _convert_perplexity_response

        response = {
            "results": [
                {"title": "Page 1", "url": "https://example.com/page1", "snippet": "First result snippet"},
                {"title": "Page 2", "url": "https://example.com/page2", "snippet": "Second result snippet"},
                {"title": "No URL", "url": "", "snippet": "Skipped"},
            ],
        }
        sources = _convert_perplexity_response(response)
        assert len(sources) == 2
        assert sources[0].url == "https://example.com/page1"
        assert sources[0].title == "Page 1"
        assert sources[0].snippet == "First result snippet"
        assert sources[1].snippet == "Second result snippet"

    @pytest.mark.asyncio
    async def test_search_calls_perplexity_api(self):
        from sgr_agent_core.tools.web_search_tool import _search_perplexity

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Result", "url": "https://example.com", "snippet": "desc"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.tools.web_search_tool.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await _search_perplexity(
                api_key="test-key",
                api_base_url="https://api.perplexity.ai/search",
                query="test query",
                max_results=5,
                offset=0,
            )

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert call_kwargs.kwargs["json"]["query"] == "test query"
            assert call_kwargs.kwargs["json"]["max_results"] == 5
            assert len(sources) == 1


class TestSerplySearchHandler:
    """Tests for Serply search handler function."""

    def test_convert_serply_response(self):
        from sgr_agent_core.tools.web_search_tool import _convert_serply_response

        response = {
            "results": [
                {"title": "Page 1", "link": "https://example.com/page1", "description": "First result"},
                {"title": "Page 2", "link": "https://example.com/page2", "description": "Second result"},
                {"title": "No URL", "link": "", "description": "Skipped"},
            ],
        }
        sources = _convert_serply_response(response)
        assert len(sources) == 2
        assert sources[0].url == "https://example.com/page1"
        assert sources[0].title == "Page 1"
        assert sources[0].snippet == "First result"
        assert sources[1].snippet == "Second result"

    def test_serply_engine_is_registered(self):
        from sgr_agent_core.tools.web_search_tool import (
            _ENGINE_DEFAULT_URLS,
            _ENGINE_HANDLERS,
            WebSearchConfig,
            _search_serply,
        )

        assert WebSearchConfig(engine="serply", api_key="key").engine == "serply"
        assert _ENGINE_HANDLERS["serply"] is _search_serply
        assert _ENGINE_DEFAULT_URLS["serply"] == "https://api.serply.io/v1/search/"

    @pytest.mark.asyncio
    async def test_search_calls_serply_api(self):
        from sgr_agent_core.tools.web_search_tool import _search_serply

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Result", "link": "https://example.com", "description": "desc"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.tools.web_search_tool.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await _search_serply(
                api_key="test-key",
                api_base_url="https://api.serply.io/v1/search/",
                query="test query",
                max_results=5,
                offset=0,
            )

            mock_client.get.assert_called_once()
            call_kwargs = mock_client.get.call_args
            assert call_kwargs.args[0] == "https://api.serply.io/v1/search/"
            assert call_kwargs.kwargs["headers"]["X-Api-Key"] == "test-key"
            assert call_kwargs.kwargs["params"] == {"q": "test query", "num": 5}
            assert len(sources) == 1
            assert sources[0].url == "https://example.com"

    @pytest.mark.asyncio
    async def test_search_passes_offset_as_start_and_caps_page_size(self):
        from sgr_agent_core.tools.web_search_tool import _search_serply

        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.tools.web_search_tool.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await _search_serply(
                api_key="test-key",
                api_base_url="https://api.serply.io/v1/search/",
                query="test query",
                max_results=20,
                offset=10,
            )

            params = mock_client.get.call_args.kwargs["params"]
            assert params["num"] == 10
            assert params["start"] == 10
            assert sources == []


class TestTavilySearchHandler:
    """Tests for Tavily search handler function."""

    def test_convert_tavily_response(self):
        from sgr_agent_core.tools.web_search_tool import _convert_tavily_response

        response = {
            "results": [
                {"title": "Test", "url": "https://example.com", "content": "Snippet", "raw_content": "Full content"},
            ]
        }
        sources = _convert_tavily_response(response)
        assert len(sources) == 1
        assert sources[0].title == "Test"
        assert sources[0].snippet == "Snippet"
        assert sources[0].full_content == "Full content"

    @pytest.mark.asyncio
    async def test_extract_calls_tavily_api(self):
        from sgr_agent_core.tools.extract_page_content_tool import ExtractPageContentConfig, ExtractPageContentTool

        config = ExtractPageContentConfig(tavily_api_key="test-key")

        mock_client = AsyncMock()
        mock_client.extract = AsyncMock(
            return_value={
                "results": [
                    {"url": "https://example.com/page", "raw_content": "Full page content"},
                ],
                "failed_results": [],
            }
        )

        with patch("sgr_agent_core.tools.extract_page_content_tool.AsyncTavilyClient", return_value=mock_client):
            sources = await ExtractPageContentTool._extract(config, urls=["https://example.com/page"])

            assert len(sources) == 1
            assert sources[0].url == "https://example.com/page"
            assert sources[0].full_content == "Full page content"
