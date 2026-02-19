from __future__ import annotations

import logging
from typing import Any

import httpx

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.models import SourceData
from sgr_agent_core.tools.base_search_tool import _BaseSearchTool, _search_registry

logger = logging.getLogger(__name__)


class PerplexitySearchTool(_BaseSearchTool):
    """Search the web using Perplexity AI search engine. Perplexity provides
    AI-powered search with synthesized answers and source citations. Use this
    tool when you specifically want to search with Perplexity.

    Returns: Page titles, URLs, and AI-synthesized snippets
    Best for: Getting AI-synthesized answers with source citations

    Usage:
        - Use SPECIFIC terms and context in queries
        - Search queries in SAME LANGUAGE as user request
        - Results include AI-generated summary alongside source URLs
    """

    _default_engine = "perplexity"

    @staticmethod
    async def _search(
        config: SearchConfig,
        query: str,
        max_results: int,
        offset: int = 0,
        include_raw_content: bool = True,
    ) -> list[SourceData]:
        """Perform search via Perplexity Search API.

        Perplexity does not support native offset — over-fetch+slice is
        applied internally when offset > 0.
        """
        if not config.perplexity_api_key:
            raise ValueError("perplexity_api_key is required for PerplexitySearchTool")

        fetch_count = max_results + offset if offset > 0 else max_results
        logger.info(f"Perplexity search: '{query}' (max_results={max_results}, offset={offset})")

        headers = {
            "Authorization": f"Bearer {config.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "query": query,
            "max_results": fetch_count,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.perplexity_api_base_url,
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

        sources = PerplexitySearchTool._convert_to_source_data(data)
        if offset > 0:
            sources = sources[offset:]
        return sources[:max_results]

    @staticmethod
    def _convert_to_source_data(response: dict) -> list[SourceData]:
        """Convert Perplexity Search API response to SourceData list."""
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


_search_registry["perplexity"] = PerplexitySearchTool
