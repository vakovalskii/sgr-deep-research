"""Tests for all tools.

This module contains simple tests for all tools:
- Initialization
- Config reading (if needed)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sgr_agent_core.agent_definition import SearchConfig
from sgr_agent_core.tools import (
    AdaptPlanTool,
    AnswerTool,
    ClarificationTool,
    CreateReportTool,
    ExtractPageContentTool,
    FinalAnswerTool,
    GeneratePlanTool,
    ReasoningTool,
    WebSearchTool,
)


class TestToolsInitialization:
    """Test that all tools can be initialized."""

    def test_clarification_tool_initialization(self):
        """Test ClarificationTool initialization."""
        tool = ClarificationTool(
            reasoning="Test",
            unclear_terms=["term1"],
            assumptions=["assumption1", "assumption2"],
            questions=["Question 1?", "Question 2?", "Question 3?"],
        )
        assert tool.tool_name == "clarificationtool"
        assert tool.reasoning == "Test"

    def test_generate_plan_tool_initialization(self):
        """Test GeneratePlanTool initialization."""
        tool = GeneratePlanTool(
            reasoning="Test",
            research_goal="Test goal",
            planned_steps=["Step 1", "Step 2", "Step 3"],
            search_strategies=["Strategy 1", "Strategy 2"],
        )
        assert tool.tool_name == "generateplantool"
        assert len(tool.planned_steps) == 3

    def test_adapt_plan_tool_initialization(self):
        """Test AdaptPlanTool initialization."""
        tool = AdaptPlanTool(
            reasoning="Test",
            original_goal="Original goal",
            new_goal="New goal",
            plan_changes=["Change 1"],
            next_steps=["Step 1", "Step 2"],
        )
        assert tool.tool_name == "adaptplantool"
        assert len(tool.next_steps) == 2

    def test_final_answer_tool_initialization(self):
        """Test FinalAnswerTool initialization."""
        from sgr_agent_core.models import AgentStatesEnum

        tool = FinalAnswerTool(
            reasoning="Test",
            completed_steps=["Step 1"],
            answer="Answer",
            status=AgentStatesEnum.COMPLETED,
        )
        assert tool.tool_name == "finalanswertool"
        assert tool.answer == "Answer"

    def test_reasoning_tool_initialization(self):
        """Test ReasoningTool initialization."""
        tool = ReasoningTool(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Test",
            plan_status="Test",
            enough_data=False,
            remaining_steps=["Next"],
            task_completed=False,
        )
        assert tool.tool_name == "reasoningtool"
        assert len(tool.reasoning_steps) == 2

    def test_web_search_tool_initialization(self):
        """Test WebSearchTool initialization."""
        tool = WebSearchTool(
            reasoning="Test",
            query="test query",
        )
        assert tool.tool_name == "websearchtool"
        assert tool.query == "test query"

    def test_extract_page_content_tool_initialization(self):
        """Test ExtractPageContentTool initialization."""
        with patch("sgr_agent_core.tools.extract_page_content_tool.TavilySearchService"):
            tool = ExtractPageContentTool(
                reasoning="Test",
                urls=["https://example.com"],
            )
            assert tool.tool_name == "extractpagecontenttool"
            assert len(tool.urls) == 1

    def test_create_report_tool_initialization(self):
        """Test CreateReportTool initialization."""
        tool = CreateReportTool(
            reasoning="Test",
            title="Test Report",
            user_request_language_reference="Test",
            content="Test content",
            confidence="high",
        )
        assert tool.tool_name == "createreporttool"
        assert tool.title == "Test Report"

    def test_answer_tool_initialization(self):
        """Test AnswerTool initialization."""
        tool = AnswerTool(
            reasoning="Sharing progress",
            intermediate_result="Found 3 relevant sources so far.",
            continue_research=True,
        )
        assert tool.tool_name == "answertool"
        assert tool.reasoning == "Sharing progress"
        assert tool.intermediate_result == "Found 3 relevant sources so far."
        assert tool.continue_research is True


class TestAnswerToolExecution:
    """Tests for AnswerTool execution."""

    @pytest.mark.asyncio
    async def test_answer_tool_returns_intermediate_result(self):
        """Test AnswerTool __call__ returns intermediate_result."""
        tool = AnswerTool(
            reasoning="Progress update",
            intermediate_result="Partial findings: X and Y.",
        )
        result = await tool(MagicMock(), MagicMock())
        assert result == "Partial findings: X and Y."


class TestToolsConfigReading:
    """Test that tools that need config can read it correctly."""

    def test_web_search_tool_reads_config(self):
        """Test WebSearchTool reads search config for max_results."""
        tool = WebSearchTool(
            reasoning="Test",
            query="test query",
            max_results=5,
        )
        # Tool should use provided max_results
        assert tool.query == "test query"
        assert tool.max_results == 5

    def test_extract_page_content_tool_reads_config(self):
        """Test ExtractPageContentTool reads search config."""
        tool = ExtractPageContentTool(
            reasoning="Test",
            urls=["https://example.com"],
        )
        # Tool should be initialized without errors
        assert len(tool.urls) == 1

    def test_create_report_tool_reads_config(self):
        """Test CreateReportTool reads execution config."""
        tool = CreateReportTool(
            reasoning="Test",
            title="Test Report",
            user_request_language_reference="Test",
            content="Test content",
            confidence="high",
        )
        # Tool should be initialized without errors
        assert tool.title == "Test Report"


class TestSearchToolsKwargs:
    """Test that search tools use kwargs (tool config) with fallback to
    config.search."""

    @pytest.mark.asyncio
    async def test_web_search_tool_uses_kwargs_over_config_search(self):
        """WebSearchTool uses max_results from kwargs when provided."""
        from sgr_agent_core.models import AgentContext

        tool = WebSearchTool(reasoning="r", query="test", max_results=5)
        context = AgentContext()
        config = MagicMock()
        config.search = SearchConfig(tavily_api_key="k", max_results=10)
        with patch("sgr_agent_core.tools.web_search_tool.TavilySearchService") as mock_svc_class:
            mock_svc = AsyncMock()
            mock_svc.search = AsyncMock(return_value=[])
            mock_svc_class.return_value = mock_svc
            await tool(context, config, max_results=3)
            call_args = mock_svc_class.call_args[0][0]
            assert call_args.max_results == 3

    @pytest.mark.asyncio
    async def test_web_search_tool_fallback_to_config_search(self):
        """WebSearchTool uses config.search when kwargs do not set
        max_results."""
        from sgr_agent_core.models import AgentContext

        tool = WebSearchTool(reasoning="r", query="test", max_results=5)
        context = AgentContext()
        config = MagicMock()
        config.search = SearchConfig(tavily_api_key="k", max_results=10)
        with patch("sgr_agent_core.tools.web_search_tool.TavilySearchService") as mock_svc_class:
            mock_svc = AsyncMock()
            mock_svc.search = AsyncMock(return_value=[])
            mock_svc_class.return_value = mock_svc
            await tool(context, config)
            call_args = mock_svc_class.call_args[0][0]
            assert call_args.max_results == 10

    @pytest.mark.asyncio
    async def test_extract_page_content_tool_uses_content_limit_from_kwargs(self):
        """ExtractPageContentTool uses content_limit from kwargs."""
        from sgr_agent_core.models import AgentContext

        tool = ExtractPageContentTool(reasoning="r", urls=["https://example.com"])
        context = AgentContext()
        config = MagicMock()
        config.search = SearchConfig(tavily_api_key="k", content_limit=1000)
        with patch("sgr_agent_core.tools.extract_page_content_tool.TavilySearchService") as mock_svc_class:
            mock_svc = AsyncMock()
            mock_svc.extract = AsyncMock(return_value=[])
            mock_svc_class.return_value = mock_svc
            await tool(context, config, content_limit=500)
            call_args = mock_svc_class.call_args[0][0]
            assert call_args.content_limit == 500
