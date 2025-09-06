from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Type

from pydantic import Field, create_model

from core.models import SearchResult
from core.prompts import PromptLoader
from core.reasoning_schemas import (
    AdaptPlan,
    Clarification,
    CreateReport,
    GeneratePlan,
    NextStep,
    ReportCompletion,
    WebSearch,
)
from services.tavily_search import TavilySearchService

if TYPE_CHECKING:
    from core.models import ResearchContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ToolCallMixin:
    """Mixin to provide tool handling capabilities
    result should be a string or dumped json"""

    def __call__(self, context: ResearchContext) -> str:
        raise NotImplementedError("Execute method must be implemented by subclass")


class ClarificationTool(ToolCallMixin, Clarification):
    def __call__(self, context: ResearchContext, config=None) -> str:
        """Handle clarification requests when facing ambiguous user requests"""

        # Mark clarification as used to prevent cycling
        context.clarifications_used += 1

        if self.unclear_terms:
            logger.info(f"❓ Unclear terms: {', '.join(self.unclear_terms)}")

        logger.info("\nCLARIFYING QUESTIONS:")
        for i, question in enumerate(self.questions, 1):
            logger.info(f"   {i}. {question}")

        if self.assumptions:
            logger.info("\nPossible interpretations:")
            for assumption in self.assumptions:
                logger.info(f"   • {assumption}")

        logger.info("\n⏸️  Research paused - please answer questions above")

        return "\n".join(self.questions)


class GeneratePlanTool(ToolCallMixin, GeneratePlan):
    def __call__(self, context: ResearchContext, config=None) -> str:
        """Generate and store research plan based on clear user request"""
        logger.info("📋 Research Plan Created:")
        logger.info(f"🎯 Goal: {self.research_goal}")
        logger.info(f"📝 Steps: {len(self.planned_steps)}")
        for i, step in enumerate(self.planned_steps, 1):
            logger.info(f"   {i}. {step}")

        return self.model_dump_json(
            indent=2,
            exclude={
                "reasoning",
            },
        )


class AdaptPlanTool(ToolCallMixin, AdaptPlan):
    def __call__(self, context: ResearchContext, config=None) -> str:
        """Adapt research plan based on new findings"""
        logger.info("\n🔄 PLAN ADAPTED")
        logger.info("📝 Changes:")
        for change in self.plan_changes:
            logger.info(f"   • {change}")
        logger.info(f"🎯 New goal {self.new_goal}")

        return self.model_dump_json(
            indent=2,
            exclude={
                "reasoning",
            },
        )


class CreateReportTool(ToolCallMixin, CreateReport):
    def __call__(self, context: ResearchContext, config=None) -> str:
        # Debug: Log CreateReport fields
        logger.info("📝 CREATE REPORT FULL DEBUG:")
        logger.info(f"   🌍 Language Reference: '{self.user_request_language_reference}'")
        logger.info(f"   📊 Title: '{self.title}'")
        logger.info(f"   🔍 Reasoning: '{self.reasoning[:150]}...'")
        logger.info(f"   📈 Confidence: {self.confidence}")
        logger.info(f"   📄 Content Preview: '{self.content[:200]}...'")
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

        report = {
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "sources_count": len(context.sources),
            "word_count": len(self.content.split()),
            "filepath": filepath,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"📄 Report Created: {self.title}")
        logger.info(f"📊 Words: {report['word_count']}, Sources: {report['sources_count']}")
        logger.info(f"💾 Saved: {filepath}")
        logger.info(f"📈 Confidence: {self.confidence}")

        return json.dumps(report, indent=2, ensure_ascii=False)


class ReportCompletionTool(ToolCallMixin, ReportCompletion):
    def __call__(self, context: ResearchContext, config=None) -> str:
        """Complete research task"""

        logger.info("\n✅ RESEARCH COMPLETED")
        logger.info(f"📋 Status: {self.status}")

        if self.completed_steps:
            logger.info("📝 Completed steps:")
            for step in self.completed_steps:
                logger.info(f"   • {step}")

        return json.dumps(
            {"tool": "report_completion", "status": self.status, "completed_steps": self.completed_steps},
            indent=2,
            ensure_ascii=False,
        )


class WebSearchTool(ToolCallMixin, WebSearch):
    def __init__(self, **data):
        super().__init__(**data)
        self._search_service = None
        self._config = None

    def __call__(self, context: ResearchContext, config=None) -> str:
        """Execute web search using TavilySearchService"""
        if self._search_service is None or self._config != config:
            self._search_service = TavilySearchService(config)
            self._config = config

        logger.info(f"🔍 Search query: '{self.query}'")

        answer, sources = self._search_service.search(
            query=self.query,
            max_results=self.max_results,
        )

        sources = TavilySearchService.rearrange_sources(sources, starting_number=len(context.sources) + 1)

        for source in sources:
            context.sources[source.url] = source

        search_result = SearchResult(
            query=self.query,
            answer=answer,
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
        logger.info(formatted_result)
        return formatted_result


class NextStepToolStub(NextStep, ToolCallMixin):
    """Stub class for correct autocomplete"""

    pass


class NextStepToolsBuilder:
    """Builder for NextStepTool with dynamic union tool function type on pydantic models level"""

    tools: ClassVar[list[Type[ToolCallMixin]]] = [
        ClarificationTool,
        GeneratePlanTool,
        WebSearchTool,
        AdaptPlanTool,
        CreateReportTool,
        ReportCompletionTool,
    ]

    @classmethod
    def _create_tool_types_union(cls, exclude: list[Type[ToolCallMixin]] | None = None):
        if exclude is None:
            exclude = []
        enabled_tools_types = [tool for tool in cls.tools if tool not in exclude]
        if len(enabled_tools_types) == 1:
            return enabled_tools_types[0]

        import operator
        from functools import reduce

        return reduce(operator.or_, enabled_tools_types)

    @classmethod
    def build_NextStepTools(
        cls, exclude: list[Type[ToolCallMixin]] | None = None, config=None
    ) -> Type[NextStepToolStub]:
        tool_prompt = PromptLoader.get_tool_function_prompt(config)
        return create_model(
            "NextStepTools",
            __base__=NextStepToolStub,
            function=(cls._create_tool_types_union(exclude), Field(description=tool_prompt)),
        )
