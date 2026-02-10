from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import AgentStatesEnum

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FinalAnswerTool(BaseTool):
    """Finalize a task and complete agent execution after all steps are
    completed.

    Usage: Call after you are ready to finalize your work and provide the final answer to the user.
    """

    reasoning: str = Field(description="Why task is now complete and how answer was verified")
    completed_steps: list[str] = Field(
        description="Summary of completed steps including verification", min_length=1, max_length=5
    )
    answer: str = Field(description="Comprehensive final answer with EXACT factual details (dates, numbers, names)")
    status: Literal[AgentStatesEnum.COMPLETED, AgentStatesEnum.FAILED] = Field(description="Task completion status")

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        context.state = self.status
        context.execution_result = self.answer
        return self.answer
