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
    direct_answer: str = Field(
        description="Concise, direct answer to the original question. Keep it SHORT and SPECIFIC (1-3 words or a simple phrase). Examples: '82 years old', 'Serban Ghenea', '11 players', 'January 2024'"
    )
    user_request_language_reference: str = Field(
        description="Copy of original user request to ensure language consistency"
    )
    calculations: str = Field(
        default="",
        description="If calculations are needed (age, dates, numbers, percentages), show step-by-step mathematical work and solution."
    )
    content: str = Field(
        description="Write comprehensive research report following the REPORT CREATION GUIDELINES from system prompt. "
        "Use the SAME LANGUAGE as user_request_language_reference."
    )
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in findings")

    def __call__(self, context: ResearchContext) -> str:
        # Validate report content is not empty
        if not self.title.strip() or not self.direct_answer.strip() or not self.content.strip():
            return "ERROR: Report validation failed. Title, direct_answer, and content cannot be empty. Please provide a complete report with actual research findings."
        
        # Mark report as created
        context.report_created = True
        
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
        
        # Add calculations section BEFORE direct answer if provided
        if self.calculations.strip():
            full_content += f"## 🧮 Calculations\n\n{self.calculations}\n\n"
        
        full_content += f"## 🎯 Direct Answer\n\n**{self.direct_answer}**\n\n"
        full_content += f"## 📊 Detailed Report\n\n"
        full_content += self.content + "\n\n"
        full_content += f"## 📚 Sources\n\n"
        full_content += "\n".join(["- " + str(source) for source in context.sources.values()])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        report = {
            "title": self.title,
            "direct_answer": self.direct_answer,
            "content": self.content,
            "confidence": self.confidence,
            "sources_count": len(context.sources),
            "word_count": len(self.content.split()),
            "filepath": filepath,
            "timestamp": datetime.now().isoformat(),
        }
        calculations_info = f"🧮 Calculations: '{self.calculations[:100]}...'" if self.calculations.strip() else "🧮 No calculations provided"
        logger.info(
            "📝 CREATE REPORT FULL DEBUG:\n"
            f"   🌍 Language Reference: '{self.user_request_language_reference}'\n"
            f"   📊 Title: '{self.title}'\n"
            f"   🎯 Direct Answer: '{self.direct_answer}'\n"
            f"   🔍 Reasoning: '{self.reasoning[:150]}...'\n"
            f"   {calculations_info}\n"
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
    max_results: int | None = Field(default=None, description="Maximum results (uses config.search.max_results if None)")
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
        
        # Use config default if max_results is None
        max_results = self.max_results if self.max_results is not None else config.search.max_results
        logger.info(f"📊 Using max_results: {max_results} (config default: {config.search.max_results})")
        logger.info(f"📄 Using scrape_content: {self.scrape_content}")

        try:
            sources = self._search_service.search(
                query=self.query,
                max_results=max_results,
                include_raw_content=self.scrape_content,
            )
        except Exception as e:
            logger.error(f"❌ Search failed: {str(e)}")
            return f"Search failed: {str(e)}. Please try again with a different query or check your Tavily API configuration."

        sources = TavilySearchService.rearrange_sources(sources, starting_number=len(context.sources) + 1)

        # Auto-extract full content from Wikipedia URLs if not already scraped
        wikipedia_urls = [s.url for s in sources if 'wikipedia.org' in s.url and not s.full_content]
        if wikipedia_urls and not self.scrape_content:
            try:
                logger.info(f"📖 Auto-extracting Wikipedia content from {len(wikipedia_urls)} URLs")
                extracted_sources = self._search_service.extract(urls=wikipedia_urls)
                
                # Update sources with extracted content
                for extracted in extracted_sources:
                    for source in sources:
                        if source.url == extracted.url:
                            source.full_content = extracted.full_content
                            source.char_count = extracted.char_count
                            logger.info(f"📄 Updated Wikipedia content for: {source.url[:60]}...")
                            break
            except Exception as e:
                logger.warning(f"⚠️ Wikipedia auto-extraction failed: {str(e)} (continuing with basic results)")

        for source in sources:
            context.sources[source.url] = source

        search_result = SearchResult(
            query=self.query,
            answer=None,
            citations=sources,
            timestamp=datetime.now(),
        )
        context.searches.append(search_result)
        
        # Clean up old searches to prevent context overflow (keep only last 1 search)
        context.cleanup_old_searches_and_save_summary(max_searches_to_keep=1)

        formatted_result = f"Search Results:\n\n"

        for source in sources:
            # Format: [1] Title
            # URL: https://example.com
            # Snippet: content here
            formatted_result += f"[{source.number}] {source.title or 'Untitled'}\n"
            formatted_result += f"URL: {source.url}\n"
            formatted_result += f"Snippet: {source.snippet}\n"
            
            if source.full_content:
                formatted_result += f"\n**Full Content (Markdown):**\n{source.full_content[:config.scraping.content_limit]}\n"
            
            formatted_result += "\n"

        context.searches_used += 1
        logger.debug(formatted_result)
        return formatted_result


class ExtractContentTool(BaseTool):
    """Extract full content from specific URLs using web scraping.
    
    Use this tool when you need to:
    - Get complete content from specific web pages
    - Deep dive into particular sources found in search results
    - Extract structured data from known URLs
    - Scrape content for detailed analysis
    """

    reasoning: str = Field(description="Why content extraction is needed from these URLs")
    urls: list[str] = Field(description="List of URLs to extract content from", min_length=1, max_length=5)

    def __init__(self, **data):
        super().__init__(**data)
        self._search_service = TavilySearchService()

    def __call__(self, context: ResearchContext) -> str:
        """Extract content from specified URLs using TavilySearchService."""

        logger.info(f"📄 Extracting content from {len(self.urls)} URLs")
        logger.info(f"📊 Using extraction_limit: {config.scraping.extraction_limit} characters")

        try:
            sources = self._search_service.extract(urls=self.urls)
            sources = TavilySearchService.rearrange_sources(sources, starting_number=len(context.sources) + 1)
        except Exception as e:
            logger.error(f"❌ Content extraction failed: {str(e)}")
            return f"Content extraction failed: {str(e)}. Please try again with different URLs or check your Tavily API configuration."

        for source in sources:
            context.sources[source.url] = source

        formatted_result = f"Extracted Content:\n\n"

        for source in sources:
            # Format: [1] Title
            # URL: https://example.com
            # Content: extracted content here
            formatted_result += f"[{source.number}] {source.title or 'Untitled'}\n"
            formatted_result += f"URL: {source.url}\n"
            
            if source.full_content:
                formatted_result += f"Content: {source.full_content[:config.scraping.extraction_limit]}\n"
            else:
                formatted_result += f"Content: {source.snippet}\n"
            
            formatted_result += "\n"

        logger.debug(f"Extracted {len(sources)} pages successfully")
        return formatted_result


research_agent_tools = [
    WebSearchTool,
    ExtractContentTool,
    CreateReportTool,
]
