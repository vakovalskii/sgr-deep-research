"""Tests for search provider logic inlined into tools (TavilySearchTool,
BraveSearchTool, PerplexitySearchTool)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData


class TestSearchToolRegistry:
    """Tests for _BaseSearchTool registry and shared helpers."""

    def test_registry_contains_all_engines(self):
        from sgr_agent_core.tools.base_search_tool import _search_registry

        # Ensure concrete tools are imported so registry is populated
        from sgr_agent_core.tools.brave_search_tool import BraveSearchTool  # noqa: F401
        from sgr_agent_core.tools.perplexity_search_tool import PerplexitySearchTool  # noqa: F401
        from sgr_agent_core.tools.tavily_search_tool import TavilySearchTool  # noqa: F401

        assert set(_search_registry) == {"tavily", "brave", "perplexity"}

    def test_rearrange_sources(self):
        from sgr_agent_core.tools.base_search_tool import _BaseSearchTool

        sources = [
            SourceData(number=0, url="https://a.com", title="A", snippet="a"),
            SourceData(number=0, url="https://b.com", title="B", snippet="b"),
        ]
        result = _BaseSearchTool._rearrange_sources(sources, starting_number=5)
        assert result[0].number == 5
        assert result[1].number == 6


class TestBraveSearchProvider:
    """Tests for BraveSearchTool provider logic."""

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self):
        from sgr_agent_core.tools.brave_search_tool import BraveSearchTool

        config = SearchConfig(engine="brave")
        with pytest.raises(ValueError, match="brave_api_key is required"):
            await BraveSearchTool._search(config, query="test", max_results=5)

    def test_convert_to_source_data(self):
        from sgr_agent_core.tools.brave_search_tool import BraveSearchTool

        response = {
            "web": {
                "results": [
                    {"title": "Test", "url": "https://example.com", "description": "A test result"},
                    {"title": "Test2", "url": "https://example2.com", "description": "Another result"},
                    {"title": "No URL", "url": "", "description": "Skipped"},
                ]
            }
        }
        sources = BraveSearchTool._convert_to_source_data(response)
        assert len(sources) == 2
        assert sources[0].title == "Test"
        assert sources[0].url == "https://example.com"
        assert sources[0].snippet == "A test result"

    @pytest.mark.asyncio
    async def test_search_calls_brave_api(self):
        from sgr_agent_core.tools.brave_search_tool import BraveSearchTool

        config = SearchConfig(engine="brave", brave_api_key="test-key", max_results=10)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result", "url": "https://example.com", "description": "desc"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.tools.brave_search_tool.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await BraveSearchTool._search(config, query="test query", max_results=5)

            mock_client.get.assert_called_once()
            call_kwargs = mock_client.get.call_args
            assert call_kwargs.kwargs["params"]["q"] == "test query"
            assert call_kwargs.kwargs["params"]["count"] == 5
            assert len(sources) == 1


class TestPerplexitySearchProvider:
    """Tests for PerplexitySearchTool provider logic."""

    @pytest.mark.asyncio
    async def test_raises_without_api_key(self):
        from sgr_agent_core.tools.perplexity_search_tool import PerplexitySearchTool

        config = SearchConfig(engine="perplexity")
        with pytest.raises(ValueError, match="perplexity_api_key is required"):
            await PerplexitySearchTool._search(config, query="test", max_results=5)

    def test_convert_to_source_data(self):
        from sgr_agent_core.tools.perplexity_search_tool import PerplexitySearchTool

        response = {
            "results": [
                {"title": "Page 1", "url": "https://example.com/page1", "snippet": "First result snippet"},
                {"title": "Page 2", "url": "https://example.com/page2", "snippet": "Second result snippet"},
                {"title": "No URL", "url": "", "snippet": "Skipped"},
            ],
        }
        sources = PerplexitySearchTool._convert_to_source_data(response)
        assert len(sources) == 2
        assert sources[0].url == "https://example.com/page1"
        assert sources[0].title == "Page 1"
        assert sources[0].snippet == "First result snippet"
        assert sources[1].snippet == "Second result snippet"

    @pytest.mark.asyncio
    async def test_search_calls_perplexity_api(self):
        from sgr_agent_core.tools.perplexity_search_tool import PerplexitySearchTool

        config = SearchConfig(engine="perplexity", perplexity_api_key="test-key", max_results=10)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Result", "url": "https://example.com", "snippet": "desc"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.tools.perplexity_search_tool.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await PerplexitySearchTool._search(config, query="test query", max_results=5)

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert call_kwargs.kwargs["json"]["query"] == "test query"
            assert call_kwargs.kwargs["json"]["max_results"] == 5
            assert len(sources) == 1


class TestTavilySearchProvider:
    """Tests for TavilySearchTool provider logic."""

    def test_convert_to_source_data(self):
        from sgr_agent_core.tools.tavily_search_tool import TavilySearchTool

        response = {
            "results": [
                {"title": "Test", "url": "https://example.com", "content": "Snippet", "raw_content": "Full content"},
            ]
        }
        sources = TavilySearchTool._convert_to_source_data(response)
        assert len(sources) == 1
        assert sources[0].title == "Test"
        assert sources[0].snippet == "Snippet"
        assert sources[0].full_content == "Full content"

    @pytest.mark.asyncio
    async def test_extract_calls_tavily_api(self):
        from sgr_agent_core.tools.tavily_search_tool import TavilySearchTool

        config = SearchConfig(tavily_api_key="test-key")

        mock_client = AsyncMock()
        mock_client.extract = AsyncMock(
            return_value={
                "results": [
                    {"url": "https://example.com/page", "raw_content": "Full page content"},
                ],
                "failed_results": [],
            }
        )

        with patch("sgr_agent_core.tools.tavily_search_tool.AsyncTavilyClient", return_value=mock_client):
            sources = await TavilySearchTool._extract(config, urls=["https://example.com/page"])

            assert len(sources) == 1
            assert sources[0].url == "https://example.com/page"
            assert sources[0].full_content == "Full page content"
