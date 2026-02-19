from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from sgr_agent_core.base_tool import SystemBaseTool

from ..models import ProgressiveDiscoveryContext
from ..services.tool_filter_service import ToolFilterService

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext


class SearchToolsTool(SystemBaseTool):
    """Search for available tools by capability description.

    Use this tool when you need a capability that is not in your current
    toolkit. Describe what you need in natural language and matching
    tools will be added to your active toolkit for subsequent use.
    """

    query: str = Field(description="Natural language description of the capability you need (e.g. 'search the web')")

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs) -> str:
        if not isinstance(context, ProgressiveDiscoveryContext):
            return "Error: context is not initialized as ProgressiveDiscoveryContext"

        if not context.all_tools:
            return "No additional tools available for discovery."

        matched = ToolFilterService.filter_tools(self.query, context.all_tools)

        already_discovered_names = {t.tool_name for t in context.discovered_tools}
        new_tools = [t for t in matched if t.tool_name not in already_discovered_names]

        if not new_tools:
            return f"No new tools found for query '{self.query}'. Already discovered: {already_discovered_names}"

        context.discovered_tools.extend(new_tools)

        summary = ToolFilterService.get_tool_summaries(new_tools)
        return (
            f"Found {len(new_tools)} new tool(s) for '{self.query}':\n{summary}\n\n"
            "These tools are now available in your toolkit. You can use them in subsequent steps."
        )
