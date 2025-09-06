import logging

from core.models import SourceData
from tavily import TavilyClient

logger = logging.getLogger(__name__)


class TavilySearchService:
    def __init__(self, config):
        self._client = TavilyClient(config.tavily.api_key)
        self._config = config

    @staticmethod
    def rearrange_sources(sources: list[SourceData], starting_number=1) -> list[SourceData]:
        for i, source in enumerate(sources, starting_number):
            source.number = i
        return sources

    def search(
        self,
        query: str,
        max_results: int | None = None,
        include_raw_content: bool = True,
    ) -> (str, list[SourceData]):
        """
        Perform search through Tavily API and return results with SourceData

        Args:
            query: Search query
            max_results: Maximum number of results (default from config)
            include_answer: Include AI answer in results
            include_raw_content: Include raw page content

        Returns:
            Tuple with tavily answer and list of SourceData
        """
        max_results = max_results or self._config.search.max_results
        logger.info(f"🔍 Tavily search: '{query}' (max_results={max_results})")

        # Execute search through Tavily
        response = self._client.search(
            query=query,
            max_results=max_results,
            include_answer=True,
            include_raw_content=include_raw_content,
        )

        # Convert results to SourceData
        sources = self._convert_to_source_data(response)

        return response.get("answer", ""), sources

    def _convert_to_source_data(self, response: dict) -> list[SourceData]:
        """Convert Tavily response to SourceData list"""
        sources = []

        for i, result in enumerate(response.get("results", [])):
            if not result.get("url", ""):
                continue

            source = SourceData(
                number=i,
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("content", ""),
            )
            if result.get("raw_content", ""):
                source.full_content = result["raw_content"]
                source.char_count = len(source.full_content)
            sources.append(source)
        return sources
