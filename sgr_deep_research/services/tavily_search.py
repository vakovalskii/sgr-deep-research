import logging

from tavily import TavilyClient

from sgr_deep_research.core.models import SourceData
from sgr_deep_research.settings import get_config

logger = logging.getLogger(__name__)


class TavilySearchService:
    def __init__(self):
        config = get_config()
        self._client = TavilyClient(api_key=config.tavily.api_key, api_base_url=config.tavily.api_base_url)
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
        """Perform search through Tavily API and return results with
        SourceData.

        Args:
            query: Search query
            max_results: Maximum number of results (default from config)
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
            include_raw_content=include_raw_content,
        )

        # Convert results to SourceData
        sources = self._convert_to_source_data(response)

        return sources

    def extract(self, urls: list[str]) -> list[SourceData]:
        """Extract content from specific URLs using Tavily API.
        
        Args:
            urls: List of URLs to extract content from
            
        Returns:
            List of SourceData with extracted content
        """
        if not urls:
            return []
            
        logger.info(f"📄 Tavily extract: {len(urls)} URLs")
        
        # Execute extract through Tavily
        response = self._client.extract(urls=urls)
        
        # Convert results to SourceData
        sources = self._convert_extract_to_source_data(response)
        
        return sources

    def _convert_extract_to_source_data(self, response: dict) -> list[SourceData]:
        """Convert Tavily extract response to SourceData list."""
        sources = []
        
        for i, result in enumerate(response.get("results", [])):
            if not result.get("url", ""):
                continue
                
            source = SourceData(
                number=i,
                title=f"Extracted Content from {result.get('url', '')}",
                url=result.get("url", ""),
                snippet=result.get("raw_content", "")[:500] + "..." if len(result.get("raw_content", "")) > 500 else result.get("raw_content", ""),
            )
            
            if result.get("raw_content", ""):
                source.full_content = result["raw_content"]
                source.char_count = len(source.full_content)
                
            sources.append(source)
            
        return sources

    def _convert_to_source_data(self, response: dict) -> list[SourceData]:
        """Convert Tavily response to SourceData list."""
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
