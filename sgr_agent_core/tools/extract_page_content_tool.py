from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, model_validator
from tavily import AsyncTavilyClient

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import SourceData

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ExtractPageContentConfig(BaseModel, extra="allow"):
    """Configuration for ExtractPageContentTool (Tavily Extract API)."""

    tavily_api_key: str | None = Field(default=None, description="Tavily API key")
    tavily_api_base_url: str = Field(default="https://api.tavily.com", description="Tavily API base URL")
    content_limit: int = Field(default=3500, gt=0, description="Content character limit per source")

    @model_validator(mode="after")
    def validate_api_key(self):
        if not self.tavily_api_key:
            raise ValueError(
                "tavily_api_key is required for ExtractPageContentTool."
                " Tavily is the only provider that supports content extraction."
            )
        return self


class ExtractPageContentTool(BaseTool):
    """Extract full detailed content from specific web pages.

    Use for: Getting complete page content from URLs found in web search.
    Returns: Full page content in readable format (via Tavily Extract API).
    Best for: Deep analysis of specific pages, extracting structured data.

    Usage: Call after WebSearchTool to get detailed information from promising URLs.

    CRITICAL WARNINGS:
        - Extracted pages may show data from DIFFERENT years/time periods than asked
        - ALWAYS verify that extracted content matches the question's temporal context
        - Example: Question asks about 2022, but page shows 2024 data - REJECT this source
        - If extracted content contradicts search snippet, prefer snippet for factual questions
        - For date/number questions, cross-check extracted values with search snippets
    """

    config_model = ExtractPageContentConfig

    reasoning: str = Field(description="Why extract these specific pages")
    urls: list[str] = Field(description="List of URLs to extract full content from", min_length=1, max_length=5)

    @staticmethod
    async def _extract(config: ExtractPageContentConfig, urls: list[str]) -> list[SourceData]:
        """Extract full content from URLs via Tavily Extract API."""
        logger.info(f"Tavily extract: {len(urls)} URLs")

        client = AsyncTavilyClient(api_key=config.tavily_api_key, api_base_url=config.tavily_api_base_url)
        response = await client.extract(urls=urls)

        sources = []
        for i, result in enumerate(response.get("results", [])):
            if not result.get("url"):
                continue

            url = result.get("url", "")
            raw_content = result.get("raw_content", "")
            source = SourceData(
                number=i,
                title=url.split("/")[-1] or "Extracted Content",
                url=url,
                snippet="",
                full_content=raw_content,
                char_count=len(raw_content),
            )
            sources.append(source)

        failed_urls = response.get("failed_results", [])
        if failed_urls:
            logger.warning(f"Failed to extract {len(failed_urls)} URLs: {failed_urls}")

        return sources

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs: Any) -> str:
        """Extract full content from specified URLs."""
        try:
            extract_config = ExtractPageContentConfig(**kwargs)
        except ValueError as e:
            return f"Error: {e}"
        logger.info(f"Extracting content from {len(self.urls)} URLs")

        sources = await self._extract(extract_config, urls=self.urls)

        # Update existing sources instead of overwriting
        for source in sources:
            if source.url in context.sources:
                # URL already exists, update with full content but keep the original number
                existing = context.sources[source.url]
                existing.full_content = source.full_content
                existing.char_count = source.char_count
            else:
                # New URL, add with next number
                source.number = len(context.sources) + 1
                context.sources[source.url] = source

        formatted_result = "Extracted Page Content:\n\n"

        # Format results using sources from context (to get correct numbers)
        for url in self.urls:
            source = context.sources.get(url)
            if source is not None:
                if source.full_content:
                    content_preview = source.full_content[: extract_config.content_limit]
                    formatted_result += (
                        f"{str(source)}\n\n**Full Content:**\n"
                        f"{content_preview}\n\n"
                        f"*[Content length: {len(content_preview)} characters]*\n\n"
                        "---\n\n"
                    )
                else:
                    formatted_result += f"{str(source)}\n*Failed to extract content*\n\n"

        logger.debug(formatted_result[:500])
        return formatted_result
