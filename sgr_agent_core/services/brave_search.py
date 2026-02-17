import logging
from typing import Any

import httpx

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData
from sgr_agent_core.services.base_search import BaseSearchService

logger = logging.getLogger(__name__)


class BraveSearchService(BaseSearchService):
    """Search service using Brave Search API.

    Uses httpx.AsyncClient for HTTP requests.
    Auth: X-Subscription-Token header.
    Brave API supports native offset for pagination.
    """

    def __init__(self, search_config: SearchConfig):
        super().__init__(search_config)
        if not search_config.brave_api_key:
            raise ValueError("brave_api_key is required for BraveSearchService")

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform search through Brave Search API.

        Brave supports native offset parameter for efficient pagination.

        Args:
            query: Search query string
            max_results: Maximum number of results (max 20 per Brave API)
            offset: Number of results to skip (native Brave API support)
            include_raw_content: Ignored for Brave (no raw content extraction)

        Returns:
            List of SourceData results
        """
        max_results = min(max_results or self._config.max_results, 20)
        logger.info(f"🔍 Brave search: '{query}' (max_results={max_results}, offset={offset})")

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._config.brave_api_key,
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
                    self._config.brave_api_base_url,
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

        return self._convert_to_source_data(data)

    def _convert_to_source_data(self, response: dict) -> list[SourceData]:
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
