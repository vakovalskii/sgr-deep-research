"""Tests for Progressive Tool Discovery example.

Covers ToolFilterService, SearchToolsTool, ProgressiveDiscoveryAgent,
and SystemBaseTool.
"""

import pytest
from pydantic import Field

from examples.progressive_discovery.models import ProgressiveDiscoveryContext
from examples.progressive_discovery.progressive_discovery_agent import ProgressiveDiscoveryAgent
from examples.progressive_discovery.services.tool_filter_service import ToolFilterService
from examples.progressive_discovery.tools.search_tools_tool import SearchToolsTool
from sgr_agent_core import PromptsConfig
from sgr_agent_core.base_tool import BaseTool, SystemBaseTool
from sgr_agent_core.models import AgentContext
from sgr_agent_core.tools import (
    AdaptPlanTool,
    ClarificationTool,
    CreateReportTool,
    FinalAnswerTool,
    GeneratePlanTool,
    ReasoningTool,
)
from tests.conftest import create_test_agent

# --- Test helpers ---


class DummySearchTool(BaseTool):
    """Search the web for information."""

    query: str = Field(default="test")

    async def __call__(self, context, config, **kwargs):
        return "search result"


class DummyExtractTool(BaseTool):
    """Extract content from a web page URL."""

    url: str = Field(default="http://example.com")

    async def __call__(self, context, config, **kwargs):
        return "extracted content"


class DummyDatabaseTool(BaseTool):
    """Query a SQL database and return results."""

    sql: str = Field(default="SELECT 1")

    async def __call__(self, context, config, **kwargs):
        return "db result"


class TestToolFilterService:
    """Tests for ToolFilterService."""

    def test_empty_query_returns_all_tools(self):
        """Empty query should return all tools unfiltered."""
        tools = [DummySearchTool, DummyExtractTool, DummyDatabaseTool]
        result = ToolFilterService.filter_tools("", tools)
        assert result == tools

    def test_empty_tools_returns_empty(self):
        """Empty tools list should return empty."""
        result = ToolFilterService.filter_tools("search", [])
        assert result == []

    def test_none_query_returns_all_tools(self):
        """None-like query should return all tools."""
        tools = [DummySearchTool, DummyExtractTool]
        result = ToolFilterService.filter_tools("   ", tools)
        assert result == tools

    def test_bm25_match_finds_relevant_tool(self):
        """BM25 should find tools with matching descriptions."""
        tools = [DummySearchTool, DummyDatabaseTool]
        result = ToolFilterService.filter_tools("search the web for information", tools)
        assert DummySearchTool in result

    def test_regex_match_finds_tool_by_keyword(self):
        """Regex should find tools with overlapping keywords."""
        tools = [DummySearchTool, DummyExtractTool, DummyDatabaseTool]
        result = ToolFilterService.filter_tools("extract content from page", tools)
        assert DummyExtractTool in result

    def test_no_matches_returns_empty(self):
        """Query with no matches should return empty list."""
        tools = [DummySearchTool, DummyExtractTool]
        result = ToolFilterService.filter_tools("zzzzxyznonexistent", tools)
        assert result == []

    def test_get_tool_summaries_format(self):
        """Tool summaries should be numbered and include name + description."""
        tools = [DummySearchTool, DummyExtractTool]
        summary = ToolFilterService.get_tool_summaries(tools)
        assert "1. dummysearchtool:" in summary
        assert "2. dummyextracttool:" in summary
        assert "Search the web" in summary


class TestSearchToolsTool:
    """Tests for SearchToolsTool."""

    def test_is_system_tool(self):
        """SearchToolsTool must be marked as system tool."""
        assert SearchToolsTool.isSystemTool is True

    @pytest.mark.asyncio
    async def test_finds_tools_and_adds_to_discovered(self):
        """Should find matching tools and add them to discovered_tools."""
        context = ProgressiveDiscoveryContext(
            all_tools=[DummySearchTool, DummyExtractTool],
        )
        tool = SearchToolsTool(query="search the web")
        result = await tool(context, config=None)

        assert DummySearchTool in context.discovered_tools
        assert "Found" in result

    @pytest.mark.asyncio
    async def test_deduplication_on_repeated_call(self):
        """Should not add already discovered tools again."""
        context = ProgressiveDiscoveryContext(
            all_tools=[DummySearchTool],
            discovered_tools=[DummySearchTool],
        )
        tool = SearchToolsTool(query="search the web")
        result = await tool(context, config=None)

        assert context.discovered_tools.count(DummySearchTool) == 1
        assert "No new tools found" in result

    @pytest.mark.asyncio
    async def test_error_on_invalid_context(self):
        """Should return error if context is not
        ProgressiveDiscoveryContext."""
        context = AgentContext()
        tool = SearchToolsTool(query="search")
        result = await tool(context, config=None)

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_no_tools_available(self):
        """Should return message when no tools available for discovery."""
        context = ProgressiveDiscoveryContext()
        tool = SearchToolsTool(query="anything")
        result = await tool(context, config=None)

        assert "No additional tools" in result


class TestProgressiveDiscoveryAgent:
    """Tests for ProgressiveDiscoveryAgent."""

    def test_context_is_progressive_discovery_context(self):
        """Agent context must be ProgressiveDiscoveryContext, not base
        AgentContext."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool],
        )
        assert isinstance(agent._context, ProgressiveDiscoveryContext)

    def test_init_splits_toolkit(self):
        """Init should separate system and non-system tools."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool, DummyExtractTool],
        )

        # System tools in toolkit
        assert ReasoningTool in agent.toolkit
        assert FinalAnswerTool in agent.toolkit
        assert SearchToolsTool in agent.toolkit

        # Non-system tools in context
        assert DummySearchTool in agent._context.all_tools
        assert DummyExtractTool in agent._context.all_tools

        # Non-system tools NOT in toolkit
        assert DummySearchTool not in agent.toolkit
        assert DummyExtractTool not in agent.toolkit

    def test_search_tools_tool_always_in_system(self):
        """SearchToolsTool should be added even if not in original toolkit."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool],
        )
        assert SearchToolsTool in agent.toolkit

    def test_get_active_tools_returns_system_plus_discovered(self):
        """_get_active_tools should return system + discovered tools."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool],
        )

        # Initially only system tools
        active = agent._get_active_tools()
        assert DummySearchTool not in active
        assert ReasoningTool in active

        # After discovery
        agent._context.discovered_tools.append(DummySearchTool)
        active = agent._get_active_tools()
        assert DummySearchTool in active

    @pytest.mark.asyncio
    async def test_prepare_tools_returns_only_active(self):
        """_prepare_tools should return pydantic_function_tool only for active
        tools."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool, DummyExtractTool],
        )

        tools = await agent._prepare_tools()
        tool_names = {t["function"]["name"] for t in tools}

        # System tools present
        assert ReasoningTool.tool_name in tool_names
        assert FinalAnswerTool.tool_name in tool_names
        assert SearchToolsTool.tool_name in tool_names

        # Non-system tools not present (not discovered yet)
        assert DummySearchTool.tool_name not in tool_names
        assert DummyExtractTool.tool_name not in tool_names

    @pytest.mark.asyncio
    async def test_prepare_context_uses_active_tools(self):
        """_prepare_context should pass active tools to system prompt."""
        prompts = PromptsConfig(
            system_prompt_str="Tools: {available_tools}",
            initial_user_request_str="Test",
            clarification_response_str="Test",
        )
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool],
            prompts_config=prompts,
        )

        context = await agent._prepare_context()
        system_msg = context[0]["content"]

        # System tools mentioned
        assert ReasoningTool.tool_name in system_msg

        # Non-system tools NOT mentioned (not discovered yet)
        assert DummySearchTool.tool_name not in system_msg


class TestSystemToolsNeverFiltered:
    """Tests that isSystemTool tools are always available and never subject to
    filtering."""

    def test_system_tools_not_in_all_tools(self):
        """System tools must never end up in all_tools (the filterable
        pool)."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, ClarificationTool, DummySearchTool, DummyDatabaseTool],
        )

        for tool in [ReasoningTool, FinalAnswerTool, ClarificationTool, SearchToolsTool]:
            assert tool not in agent._context.all_tools, f"System tool {tool.__name__} should not be in filterable pool"

    def test_non_system_tools_only_in_all_tools(self):
        """Only non-system tools should be in the filterable pool."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool, DummyExtractTool, DummyDatabaseTool],
        )

        assert set(agent._context.all_tools) == {DummySearchTool, DummyExtractTool, DummyDatabaseTool}

    def test_system_tools_persist_after_search_with_no_results(self):
        """System tools must remain active even when search finds nothing."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool],
        )

        active = agent._get_active_tools()
        assert ReasoningTool in active
        assert FinalAnswerTool in active
        assert SearchToolsTool in active

    @pytest.mark.asyncio
    async def test_system_tools_persist_after_discovery(self):
        """System tools must remain in active toolkit after discovering new
        tools."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, DummySearchTool, DummyExtractTool],
        )

        # Simulate discovery
        tool = SearchToolsTool(query="search the web")
        await tool(agent._context, config=None)

        active = agent._get_active_tools()
        # System tools still there
        assert ReasoningTool in active
        assert FinalAnswerTool in active
        assert SearchToolsTool in active
        # Discovered tool also there
        assert DummySearchTool in active

    @pytest.mark.asyncio
    async def test_prepare_tools_always_includes_system_tools(self):
        """_prepare_tools must always include system tools regardless of
        discovered state."""
        agent = create_test_agent(
            ProgressiveDiscoveryAgent,
            toolkit=[ReasoningTool, FinalAnswerTool, GeneratePlanTool, DummySearchTool, DummyDatabaseTool],
        )

        tools = await agent._prepare_tools()
        tool_names = {t["function"]["name"] for t in tools}

        # All system tools present
        assert ReasoningTool.tool_name in tool_names
        assert FinalAnswerTool.tool_name in tool_names
        assert GeneratePlanTool.tool_name in tool_names
        assert SearchToolsTool.tool_name in tool_names

        # Non-system tools absent (not yet discovered)
        assert DummySearchTool.tool_name not in tool_names
        assert DummyDatabaseTool.tool_name not in tool_names


class TestIsSystemTool:
    """Tests for isSystemTool ClassVar on BaseTool and SystemBaseTool."""

    def test_base_tool_default_is_false(self):
        """BaseTool.isSystemTool should default to False."""
        assert BaseTool.isSystemTool is False

    def test_system_base_tool_is_true(self):
        """SystemBaseTool.isSystemTool should be True."""
        assert SystemBaseTool.isSystemTool is True

    def test_subclass_of_system_base_tool_inherits_true(self):
        """Subclass of SystemBaseTool should inherit isSystemTool = True."""

        class MySystemTool(SystemBaseTool):
            pass

        assert MySystemTool.isSystemTool is True
        assert issubclass(MySystemTool, SystemBaseTool)

    def test_subclass_inherits_false(self):
        """Subclass without override should inherit False."""

        class MyRegularTool(BaseTool):
            pass

        assert MyRegularTool.isSystemTool is False
        assert not issubclass(MyRegularTool, SystemBaseTool)

    def test_core_system_tools_marked(self):
        """All core system tools should inherit from SystemBaseTool."""
        system_tools = [
            ReasoningTool,
            ClarificationTool,
            FinalAnswerTool,
            GeneratePlanTool,
            AdaptPlanTool,
            CreateReportTool,
        ]
        for tool in system_tools:
            assert issubclass(tool, SystemBaseTool), f"{tool.__name__} should inherit from SystemBaseTool"
            assert tool.isSystemTool is True, f"{tool.__name__} should have isSystemTool=True"
