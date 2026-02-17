"""Tests for search services (BaseSearchService, TavilySearchService,
BraveSearchService, PerplexitySearchService)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData


class TestBaseSearchService:
    """Tests for BaseSearchService."""

    def test_factory_creates_tavily_service(self):
        from sgr_agent_core.services.base_search import BaseSearchService
        from sgr_agent_core.services.tavily_search import TavilySearchService

        config = SearchConfig(engine="tavily", tavily_api_key="test-key")
        service = BaseSearchService.create(config)
        assert isinstance(service, TavilySearchService)

    def test_factory_creates_brave_service(self):
        from sgr_agent_core.services.base_search import BaseSearchService
        from sgr_agent_core.services.brave_search import BraveSearchService

        config = SearchConfig(engine="brave", brave_api_key="test-key")
        service = BaseSearchService.create(config)
        assert isinstance(service, BraveSearchService)

    def test_factory_creates_perplexity_service(self):
        from sgr_agent_core.services.base_search import BaseSearchService
        from sgr_agent_core.services.perplexity_search import PerplexitySearchService

        config = SearchConfig(engine="perplexity", perplexity_api_key="test-key")
        service = BaseSearchService.create(config)
        assert isinstance(service, PerplexitySearchService)

    def test_factory_raises_for_unknown_engine(self):
        from sgr_agent_core.services.base_search import BaseSearchService

        # Use model_construct to bypass Literal validation and force an invalid engine
        config = SearchConfig.model_construct(engine="unknown", tavily_api_key="k")
        with pytest.raises(ValueError, match="Unsupported search engine"):
            BaseSearchService.create(config)

    def test_rearrange_sources(self):
        from sgr_agent_core.services.base_search import BaseSearchService

        sources = [
            SourceData(number=0, url="https://a.com", title="A", snippet="a"),
            SourceData(number=0, url="https://b.com", title="B", snippet="b"),
        ]
        result = BaseSearchService.rearrange_sources(sources, starting_number=5)
        assert result[0].number == 5
        assert result[1].number == 6

    @pytest.mark.asyncio
    async def test_base_search_raises_not_implemented(self):
        from sgr_agent_core.services.base_search import BaseSearchService

        config = SearchConfig(tavily_api_key="k")
        service = BaseSearchService(config)
        with pytest.raises(NotImplementedError):
            await service.search("test")


class TestBraveSearchService:
    """Tests for BraveSearchService."""

    def test_raises_without_api_key(self):
        from sgr_agent_core.services.brave_search import BraveSearchService

        config = SearchConfig(engine="brave")
        with pytest.raises(ValueError, match="brave_api_key is required"):
            BraveSearchService(config)

    def test_convert_to_source_data(self):
        from sgr_agent_core.services.brave_search import BraveSearchService

        config = SearchConfig(engine="brave", brave_api_key="test-key")
        service = BraveSearchService(config)
        response = {
            "web": {
                "results": [
                    {"title": "Test", "url": "https://example.com", "description": "A test result"},
                    {"title": "Test2", "url": "https://example2.com", "description": "Another result"},
                    {"title": "No URL", "url": "", "description": "Skipped"},
                ]
            }
        }
        sources = service._convert_to_source_data(response)
        assert len(sources) == 2
        assert sources[0].title == "Test"
        assert sources[0].url == "https://example.com"
        assert sources[0].snippet == "A test result"

    @pytest.mark.asyncio
    async def test_search_calls_brave_api(self):
        from sgr_agent_core.services.brave_search import BraveSearchService

        config = SearchConfig(engine="brave", brave_api_key="test-key", max_results=10)
        service = BraveSearchService(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result", "url": "https://example.com", "description": "desc"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.services.brave_search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await service.search("test query", max_results=5)

            mock_client.get.assert_called_once()
            call_kwargs = mock_client.get.call_args
            assert call_kwargs.kwargs["params"]["q"] == "test query"
            assert call_kwargs.kwargs["params"]["count"] == 5
            assert len(sources) == 1


class TestPerplexitySearchService:
    """Tests for PerplexitySearchService."""

    def test_raises_without_api_key(self):
        from sgr_agent_core.services.perplexity_search import PerplexitySearchService

        config = SearchConfig(engine="perplexity")
        with pytest.raises(ValueError, match="perplexity_api_key is required"):
            PerplexitySearchService(config)

    def test_convert_to_source_data(self):
        from sgr_agent_core.services.perplexity_search import PerplexitySearchService

        config = SearchConfig(engine="perplexity", perplexity_api_key="test-key")
        service = PerplexitySearchService(config)
        response = {
            "results": [
                {"title": "Page 1", "url": "https://example.com/page1", "snippet": "First result snippet"},
                {"title": "Page 2", "url": "https://example.com/page2", "snippet": "Second result snippet"},
                {"title": "No URL", "url": "", "snippet": "Skipped"},
            ],
        }
        sources = service._convert_to_source_data(response)
        assert len(sources) == 2
        assert sources[0].url == "https://example.com/page1"
        assert sources[0].title == "Page 1"
        assert sources[0].snippet == "First result snippet"
        assert sources[1].snippet == "Second result snippet"

    @pytest.mark.asyncio
    async def test_search_calls_perplexity_api(self):
        from sgr_agent_core.services.perplexity_search import PerplexitySearchService

        config = SearchConfig(engine="perplexity", perplexity_api_key="test-key", max_results=10)
        service = PerplexitySearchService(config)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Result", "url": "https://example.com", "snippet": "desc"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("sgr_agent_core.services.perplexity_search.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            sources = await service.search("test query", max_results=5)

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert call_kwargs.kwargs["json"]["query"] == "test query"
            assert call_kwargs.kwargs["json"]["max_results"] == 5
            assert len(sources) == 1


class TestTavilySearchService:
    """Tests for TavilySearchService with BaseSearchService inheritance."""

    def test_inherits_rearrange_sources(self):
        """TavilySearchService should have rearrange_sources from
        BaseSearchService."""
        from sgr_agent_core.services.base_search import BaseSearchService
        from sgr_agent_core.services.tavily_search import TavilySearchService

        assert TavilySearchService.rearrange_sources is BaseSearchService.rearrange_sources

    def test_convert_to_source_data(self):
        from sgr_agent_core.services.tavily_search import TavilySearchService

        config = SearchConfig(tavily_api_key="test-key")
        service = TavilySearchService(config)
        response = {
            "results": [
                {"title": "Test", "url": "https://example.com", "content": "Snippet", "raw_content": "Full content"},
            ]
        }
        sources = service._convert_to_source_data(response)
        assert len(sources) == 1
        assert sources[0].title == "Test"
        assert sources[0].snippet == "Snippet"
        assert sources[0].full_content == "Full content"
