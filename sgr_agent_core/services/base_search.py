import logging
from typing import TYPE_CHECKING

from sgr_agent_core.models import SourceData

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import SearchConfig

logger = logging.getLogger(__name__)


class BaseSearchService:
    """Base class for search service providers.

    Subclasses must implement the `search` method.
    """

    def __init__(self, search_config: "SearchConfig"):
        self._config = search_config

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform a search and return results as SourceData list.

        Each provider handles offset internally:
        - Brave: uses native API offset parameter
        - Tavily/Perplexity: over-fetch+slice

        Args:
            query: Search query string
            max_results: Maximum number of results to return (after offset)
            offset: Number of results to skip
            include_raw_content: Whether to include raw page content

        Returns:
            List of SourceData results (at most max_results items)
        """
        raise NotImplementedError("Subclasses must implement search()")

    @staticmethod
    def rearrange_sources(sources: list[SourceData], starting_number: int = 1) -> list[SourceData]:
        """Renumber sources sequentially starting from given number."""
        for i, source in enumerate(sources, starting_number):
            source.number = i
        return sources

    @classmethod
    def create(cls, config: "SearchConfig") -> "BaseSearchService":
        """Factory method to create a search service based on config.engine.

        Args:
            config: SearchConfig with engine and API keys

        Returns:
            Appropriate search service instance

        Raises:
            ValueError: If engine is not supported
        """
        from sgr_agent_core.services.brave_search import BraveSearchService
        from sgr_agent_core.services.perplexity_search import PerplexitySearchService
        from sgr_agent_core.services.tavily_search import TavilySearchService

        engine = config.engine
        logger.debug(f"Creating search service for engine: {engine}")
        if engine == "tavily":
            return TavilySearchService(config)
        elif engine == "brave":
            return BraveSearchService(config)
        elif engine == "perplexity":
            return PerplexitySearchService(config)
        else:
            logger.error(f"Unsupported search engine requested: {engine}")
            raise ValueError(f"Unsupported search engine: {engine}")
