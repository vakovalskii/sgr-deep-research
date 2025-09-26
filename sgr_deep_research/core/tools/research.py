from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from sgr_deep_research.core.models import SearchResult
from sgr_deep_research.core.tools.base import BaseTool
from sgr_deep_research.services.tavily_search import TavilySearchService
from sgr_deep_research.settings import get_config

if TYPE_CHECKING:
    from sgr_deep_research.core.models import ResearchContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
config = get_config()


class CreateReportTool(BaseTool):
    """Create comprehensive detailed report with citations as a final step of
    research."""

    reasoning: str = Field(description="Why ready to create report now")
    title: str = Field(description="Report title")
    user_request_language_reference: str = Field(
        description="Copy of original user request to ensure language consistency"
    )
    content: str = Field(
        description="Write comprehensive research report following the REPORT CREATION GUIDELINES from system prompt. "
        "Use the SAME LANGUAGE as user_request_language_reference."
    )
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in findings")

    def __call__(self, context: ResearchContext) -> str:
        # Save report
        reports_dir = config.execution.reports_dir
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in self.title if c.isalnum() or c in (" ", "-", "_"))[:50]
        filename = f"{timestamp}_{safe_title}.md"
        filepath = os.path.join(reports_dir, filename)

        # Format full report with sources
        full_content = f"# {self.title}\n\n"
        full_content += f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        full_content += self.content + "\n\n"
        full_content += "\n".join(["- " + str(source) for source in context.sources.values()])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        # Mark that report has been created
        try:
            context.report_created = True
        except (AttributeError, ValueError):
            # Fallback for older context objects without this field
            pass
        
        report = {
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "sources_count": len(context.sources),
            "word_count": len(self.content.split()),
            "filepath": filepath,
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(
            "📝 CREATE REPORT FULL DEBUG:\n"
            f"   🌍 Language Reference: '{self.user_request_language_reference}'\n"
            f"   📊 Title: '{self.title}'\n"
            f"   🔍 Reasoning: '{self.reasoning[:150]}...'\n"
            f"   📈 Confidence: {self.confidence}\n"
            f"   📄 Content Preview: '{self.content[:200]}...'\n"
            f"   📊 Words: {report['word_count']}, Sources: {report['sources_count']}\n"
            f"   💾 Saved: {filepath}\n"
        )
        return json.dumps(report, indent=2, ensure_ascii=False)


class WebSearchTool(BaseTool):
    """Gather information.

    - Use SPECIFIC terms and context in search queries
    - For acronyms like "SGR", add context: "SGR Schema-Guided Reasoning"
    - Use quotes for exact phrases: "Structured Output OpenAI"
    - SEARCH QUERIES in SAME LANGUAGE as user request
    - scrape_content=True for deeper analysis (fetches full page content)
    """

    reasoning: str = Field(description="Why this search is needed and what to expect")
    query: str = Field(description="Search query in same language as user request")
    max_results: int = Field(default=10, description="Maximum results", ge=1, le=10)
    scrape_content: bool = Field(
        default=False,
        description="Fetch full page content for deeper analysis",
    )

    def __init__(self, **data):
        super().__init__(**data)
        self._search_service = TavilySearchService()

    def __call__(self, context: ResearchContext) -> str:
        """Execute web search using TavilySearchService."""

        logger.info(f"🔍 Search query: '{self.query}'")

        sources = self._search_service.search(
            query=self.query,
            max_results=self.max_results,
        )

        sources = TavilySearchService.rearrange_sources(sources, starting_number=len(context.sources) + 1)

        for source in sources:
            context.sources[source.url] = source

        search_result = SearchResult(
            query=self.query,
            answer=None,
            citations=sources,
            timestamp=datetime.now(),
        )
        context.searches.append(search_result)

        formatted_result = f"Search Query: {search_result.query}\n\n"

        if search_result.answer:
            formatted_result += f"AI Answer: {search_result.answer}\n\n"

        formatted_result += "Search Results:\n\n"

        for source in sources:
            if source.full_content:
                formatted_result += (
                    f"{str(source)}\n\n**Full Content (Markdown):**\n"
                    f"{source.full_content[: config.scraping.content_limit]}\n\n"
                )
            else:
                formatted_result += f"{str(source)}\n{source.snippet}\n\n"

        context.searches_used += 1
        logger.debug(formatted_result)
        return formatted_result


research_agent_tools = [
    WebSearchTool,
    CreateReportTool,
]
