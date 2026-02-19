from __future__ import annotations

from typing import Type

from openai import AsyncOpenAI, pydantic_function_tool

from sgr_agent_core.agent_definition import AgentConfig
from sgr_agent_core.agents.sgr_tool_calling_agent import SGRToolCallingAgent
from sgr_agent_core.base_tool import BaseTool, SystemBaseTool
from sgr_agent_core.services.prompt_loader import PromptLoader

from .models import ProgressiveDiscoveryContext
from .tools.search_tools_tool import SearchToolsTool


class ProgressiveDiscoveryAgent(SGRToolCallingAgent):
    """Agent that starts with minimal system tools and dynamically discovers
    additional tools via SearchToolsTool.

    On init, splits the toolkit into:
    - system tools (subclasses of SystemBaseTool) -> self.toolkit (always available)
    - non-system tools -> stored in context.all_tools

    SearchToolsTool is automatically added if not already present.
    Discovered tools accumulate in context.discovered_tools.
    """

    name: str = "progressive_discovery_agent"

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        system_tools = [t for t in toolkit if issubclass(t, SystemBaseTool)]
        non_system_tools = [t for t in toolkit if not issubclass(t, SystemBaseTool)]

        if SearchToolsTool not in system_tools:
            system_tools.append(SearchToolsTool)

        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=system_tools,
            def_name=def_name,
            **kwargs,
        )

        self._context = ProgressiveDiscoveryContext(
            all_tools=non_system_tools,
        )

    def _get_active_tools(self) -> list[Type[BaseTool]]:
        """Return system tools + discovered tools."""
        return list(self.toolkit) + list(self._context.discovered_tools)

    async def _prepare_tools(self) -> list[dict]:
        """Override to return only active tools (system + discovered)."""
        active_tools = self._get_active_tools()
        if self._context.iteration >= self.config.execution.max_iterations:
            raise RuntimeError("Max iterations reached")
        return [pydantic_function_tool(tool, name=tool.tool_name) for tool in active_tools]

    async def _prepare_context(self) -> list[dict]:
        """Override to pass only active tools to system prompt."""
        active_tools = self._get_active_tools()
        return [
            {"role": "system", "content": PromptLoader.get_system_prompt(active_tools, self.config.prompts)},
            *self.task_messages,
            {"role": "user", "content": PromptLoader.get_initial_user_request(self.task_messages, self.config.prompts)},
            *self.conversation,
        ]
