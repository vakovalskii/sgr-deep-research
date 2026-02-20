from __future__ import annotations

import logging
from typing import Any

import httpx

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData
from sgr_agent_core.services.registry import SearchProviderRegistry
from sgr_agent_core.tools.base_search_tool import _BaseSearchTool

logger = logging.getLogger(__name__)


class BraveSearchTool(_BaseSearchTool):
    """Search the web using Brave search engine. Brave Search provides privacy-
    focused search results with native pagination support. Use this tool when
    you specifically want to search with Brave.

    Returns: Page titles, URLs, and short snippets
    Best for: Privacy-focused search, efficient pagination via native offset

    Usage:
        - Use SPECIFIC terms and context in queries
        - Search queries in SAME LANGUAGE as user request
        - Brave supports efficient pagination with offset parameter
    """

    _default_engine = "brave"

    @staticmethod
    async def _search(
        config: SearchConfig,
        query: str,
        max_results: int,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform search via Brave Search API.

        Brave supports native offset parameter for efficient pagination.
        """
        if not config.brave_api_key:
            raise ValueError("brave_api_key is required for BraveSearchTool")

        max_results = min(max_results, 20)
        logger.info(f"Brave search: '{query}' (max_results={max_results}, offset={offset})")

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": config.brave_api_key,
        }
        params: dict[str, Any] = {
            "q": query,
            "count": max_results,
        }
        if offset > 0:
            params["offset"] = offset

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    config.brave_api_base_url,
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Brave API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Brave API request error: {e}")
            raise

        return BraveSearchTool._convert_to_source_data(data)

    @staticmethod
    def _convert_to_source_data(response: dict) -> list[SourceData]:
        """Convert Brave Search API response to SourceData list."""
        sources = []
        web_results = response.get("web", {}).get("results", [])

        for i, result in enumerate(web_results):
            url = result.get("url", "")
            if not url:
                continue

            source = SourceData(
                number=i,
                title=result.get("title", ""),
                url=url,
                snippet=result.get("description", ""),
            )
            sources.append(source)

        return sources


SearchProviderRegistry.register(BraveSearchTool, name="brave")
