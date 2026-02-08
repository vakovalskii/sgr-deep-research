"""Answer tool for sharing intermediate results and keeping agent available for
further interaction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from sgr_agent_core.base_tool import BaseTool

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

# Key in context.custom_context to signal "pass turn to user" (used by DialogAgent)
PASS_TURN_TO_USER_KEY = "pass_turn_to_user"


class AnswerTool(BaseTool):
    """Share intermediate results and keep agent available for further
    interaction.

    Use this tool to share progress updates, partial findings, or intermediate
    results with the user while keeping the agent active for continued conversation.
    Keep all fields concise - brief reasoning and clear intermediate result.
    """

    reasoning: str = Field(
        description="Why this intermediate result is being shared (1-2 sentences MAX)",
        max_length=200,
    )
    intermediate_result: str = Field(
        description="The intermediate result or progress update to share with the user (clear and informative)",
        min_length=10,
        max_length=2000,
    )
    continue_research: bool = Field(
        default=True,
        description="Whether to continue research after sharing this result (default: True)",
    )

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        """Return the intermediate result and signal agent to pass turn to
        user."""
        if context.custom_context is None:
            context.custom_context = {}
        context.custom_context[PASS_TURN_TO_USER_KEY] = True
        return self.intermediate_result
