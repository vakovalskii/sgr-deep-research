from __future__ import annotations

import logging

from tavily import AsyncTavilyClient

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData
from sgr_agent_core.services.registry import SearchProviderRegistry
from sgr_agent_core.tools.base_search_tool import _BaseSearchTool

logger = logging.getLogger(__name__)


class TavilySearchTool(_BaseSearchTool):
    """Search the web using Tavily search engine. Tavily provides high-quality
    search results with optional raw content extraction. Use this tool when you
    specifically want to search with Tavily.

    Returns: Page titles, URLs, and short snippets
    Best for: General web search, research queries

    Usage:
        - Use SPECIFIC terms and context in queries
        - Search queries in SAME LANGUAGE as user request
        - Use ExtractPageContentTool to get full content from found URLs
    """

    _default_engine = "tavily"

    @staticmethod
    async def _search(
        config: SearchConfig,
        query: str,
        max_results: int,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform search via Tavily API.

        Offset: over-fetch+slice.
        """
        fetch_count = max_results + offset if offset > 0 else max_results
        logger.info(f"Tavily search: '{query}' (max_results={max_results}, offset={offset})")

        client = AsyncTavilyClient(api_key=config.tavily_api_key, api_base_url=config.tavily_api_base_url)
        response = await client.search(query=query, max_results=fetch_count, include_raw_content=include_raw_content)

        sources = TavilySearchTool._convert_to_source_data(response)
        if offset > 0:
            sources = sources[offset:]
        return sources[:max_results]

    @staticmethod
    def _convert_to_source_data(response: dict) -> list[SourceData]:
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


SearchProviderRegistry.register(TavilySearchTool, name="tavily")
