import logging
from typing import Any

import httpx

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData
from sgr_agent_core.services.base_search import BaseSearchService

logger = logging.getLogger(__name__)


class PerplexitySearchService(BaseSearchService):
    """Search service using Perplexity Search API.

    Uses httpx.AsyncClient for HTTP requests to the dedicated Search API
    endpoint (POST /search) which returns ranked web results with titles,
    URLs, and snippets.
    Auth: Authorization Bearer header.
    Offset is handled by over-fetch+slice (no native offset support).
    """

    def __init__(self, search_config: SearchConfig):
        super().__init__(search_config)
        if not search_config.perplexity_api_key:
            raise ValueError("perplexity_api_key is required for PerplexitySearchService")

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform search through Perplexity Search API.

        Perplexity does not support native offset — over-fetch+slice
        is applied internally when offset > 0.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            offset: Number of results to skip (over-fetch+slice internally)
            include_raw_content: Ignored for Perplexity

        Returns:
            List of SourceData results
        """
        max_results = max_results or self._config.max_results
        fetch_count = max_results + offset if offset > 0 else max_results
        logger.info(f"🔍 Perplexity search: '{query}' (max_results={max_results}, offset={offset})")

        headers = {
            "Authorization": f"Bearer {self._config.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "query": query,
            "max_results": fetch_count,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._config.perplexity_api_base_url,
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Perplexity API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Perplexity API request error: {e}")
            raise

        sources = self._convert_to_source_data(data)
        if offset > 0:
            sources = sources[offset:]
        return sources[:max_results]

    def _convert_to_source_data(self, response: dict) -> list[SourceData]:
        """Convert Perplexity Search API response to SourceData list.

        Perplexity Search API returns results[] with title, url,
        snippet.
        """
        sources = []
        results = response.get("results", [])

        for i, result in enumerate(results):
            url = result.get("url", "")
            if not url:
                continue

            source = SourceData(
                number=i,
                title=result.get("title", ""),
                url=url,
                snippet=result.get("snippet", ""),
            )
            sources.append(source)

        return sources
