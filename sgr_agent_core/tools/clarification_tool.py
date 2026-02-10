from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import AgentContext, AgentStatesEnum

if TYPE_CHECKING:
    from sgr_agent_core.agent_config import AgentConfig


class ClarificationTool(BaseTool):
    """Ask clarifying questions when facing an ambiguous request.

    Keep all fields concise - brief reasoning, short terms, and clear questions.
    """

    reasoning: str = Field(description="Why clarification is needed (1-2 sentences MAX)", max_length=200)
    unclear_terms: list[str] = Field(
        description="List of unclear terms (brief, 1-3 words each)",
        min_length=1,
        max_length=3,
    )
    assumptions: list[str] = Field(
        description="Possible interpretations (short, 1 sentence each)",
        min_length=2,
        max_length=3,
    )
    questions: list[str] = Field(
        description="3 specific clarifying questions (short and direct)",
        min_length=1,
        max_length=3,
    )

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
        context.execution_result = "\n".join(self.questions)
        return ""
