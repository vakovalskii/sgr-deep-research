import logging

from tavily import AsyncTavilyClient

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData
from sgr_agent_core.services.base_search import BaseSearchService

logger = logging.getLogger(__name__)


class TavilySearchService(BaseSearchService):
    def __init__(self, search_config: SearchConfig):
        super().__init__(search_config)
        self._client = AsyncTavilyClient(
            api_key=search_config.tavily_api_key, api_base_url=search_config.tavily_api_base_url
        )

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform search through Tavily API and return results with
        SourceData.

        Tavily API does not support native offset — over-fetch+slice is
        applied internally when offset > 0.
        """
        max_results = max_results or self._config.max_results
        fetch_count = max_results + offset if offset > 0 else max_results
        logger.info(f"🔍 Tavily search: '{query}' (max_results={max_results}, offset={offset})")

        response = await self._client.search(
            query=query,
            max_results=fetch_count,
            include_raw_content=include_raw_content,
        )

        sources = self._convert_to_source_data(response)
        if offset > 0:
            sources = sources[offset:]
        return sources[:max_results]

    async def extract(self, urls: list[str]) -> list[SourceData]:
        """Extract full content from specific URLs using Tavily Extract API."""
        logger.info(f"📄 Tavily extract: {len(urls)} URLs")

        response = await self._client.extract(urls=urls)

        sources = []
        for i, result in enumerate(response.get("results", [])):
            if not result.get("url"):
                continue

            source = SourceData(
                number=i,
                title=result.get("url", "").split("/")[-1] or "Extracted Content",
                url=result.get("url", ""),
                snippet="",
                full_content=result.get("raw_content", ""),
                char_count=len(result.get("raw_content", "")),
            )
            sources.append(source)

        failed_urls = response.get("failed_results", [])
        if failed_urls:
            logger.warning(f"⚠️ Failed to extract {len(failed_urls)} URLs: {failed_urls}")

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
