"""Agents with disabled CreateReportTool.

These agents are based on existing research agents but exclude
CreateReportTool from their toolkit, allowing them to work without
generating report files.
"""

from typing import Type

from openai import AsyncOpenAI, pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_agent_core.agent_config import AgentConfig
from sgr_agent_core.agents.sgr_agent import SGRAgent
from sgr_agent_core.agents.sgr_tool_calling_agent import SGRToolCallingAgent
from sgr_agent_core.agents.tool_calling_agent import ToolCallingAgent
from sgr_agent_core.tools import (
    BaseTool,
    ClarificationTool,
    ExtractPageContentTool,
    FinalAnswerTool,
    NextStepToolsBuilder,
    NextStepToolStub,
    ReasoningTool,
    WebSearchTool,
)


class ResearchSGRAgentNoReporting(SGRAgent):
    """Research agent without CreateReportTool."""

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        # Exclude CreateReportTool from research_toolkit
        research_toolkit = [WebSearchTool, ExtractPageContentTool, FinalAnswerTool]
        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=research_toolkit + [t for t in toolkit if t not in research_toolkit],
            def_name=def_name,
            **kwargs,
        )

    async def _prepare_tools(self) -> Type[NextStepToolStub]:
        """Prepare available tools for the current agent state and progress."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.config.execution.max_iterations:
            # Only FinalAnswerTool available when max_iterations reached (no CreateReportTool)
            tools = {
                FinalAnswerTool,
            }
        if self._context.clarifications_used >= self.config.execution.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        search_config = self.get_tool_config(WebSearchTool)
        if self._context.searches_used >= search_config.max_searches:
            tools -= {
                WebSearchTool,
            }
        return NextStepToolsBuilder.build_NextStepTools(list(tools))


class ResearchToolCallingAgentNoReporting(ToolCallingAgent):
    """Tool calling research agent without CreateReportTool."""

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        # Exclude CreateReportTool from research_toolkit
        research_toolkit = [WebSearchTool, ExtractPageContentTool, FinalAnswerTool]
        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=research_toolkit + [t for t in toolkit if t not in research_toolkit],
            def_name=def_name,
            **kwargs,
        )

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for the current agent state and progress."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.config.execution.max_iterations:
            # Only FinalAnswerTool available when max_iterations reached (no CreateReportTool)
            tools = {
                FinalAnswerTool,
            }
        if self._context.clarifications_used >= self.config.execution.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        search_config = self.get_tool_config(WebSearchTool)
        if self._context.searches_used >= search_config.max_searches:
            tools -= {
                WebSearchTool,
            }
        return [pydantic_function_tool(tool, name=tool.tool_name, description="") for tool in tools]


class ResearchSGRToolCallingAgentNoReporting(SGRToolCallingAgent):
    """SGR tool calling research agent without CreateReportTool."""

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        # Exclude CreateReportTool from research_toolkit
        research_toolkit = [WebSearchTool, ExtractPageContentTool, FinalAnswerTool]
        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=research_toolkit + [t for t in toolkit if t not in research_toolkit],
            def_name=def_name,
            **kwargs,
        )

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for the current agent state and progress."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.config.execution.max_iterations:
            # Only ReasoningTool and FinalAnswerTool available when max_iterations reached (no CreateReportTool)
            tools = {
                ReasoningTool,
                FinalAnswerTool,
            }
        if self._context.clarifications_used >= self.config.execution.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        search_config = self.get_tool_config(WebSearchTool)
        if self._context.searches_used >= search_config.max_searches:
            tools -= {
                WebSearchTool,
            }
        return [pydantic_function_tool(tool, name=tool.tool_name, description="") for tool in tools]
