from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import Field

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import AgentStatesEnum

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FinalAnswerToolOWUI(BaseTool):
    """Special tool for Open-WebUI to trigger final answer generation.
    
    When ready_to_answer is True, the agent will generate a comprehensive
    final answer using LLM completion without tools.
    
    Usage: Call when you have enough information to provide a complete answer.
    """

    reasoning: str = Field(
        description="Why you are ready to provide the final answer now (1-2 sentences)",
        max_length=300,
    )
    ready_to_answer: bool = Field(
        description="Set to True when ready to generate final answer",
        default=True,
    )

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        # Mark context as ready for final answer generation
        context.state = AgentStatesEnum.COMPLETED
        return self.model_dump_json(indent=2)




