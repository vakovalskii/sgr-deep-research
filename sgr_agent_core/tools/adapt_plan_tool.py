from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from sgr_agent_core.base_tool import BaseTool

if TYPE_CHECKING:
    from sgr_agent_core.agent_config import AgentConfig
    from sgr_agent_core.models import AgentContext


class AdaptPlanTool(BaseTool):
    """Adapt a research plan based on new findings."""

    reasoning: str = Field(description="Why plan needs adaptation based on new data")
    original_goal: str = Field(description="Original research goal")
    new_goal: str = Field(description="Updated research goal")
    plan_changes: list[str] = Field(description="Specific changes made to plan", min_length=1, max_length=3)
    next_steps: list[str] = Field(description="Updated remaining steps", min_length=2, max_length=4)

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        return ""
