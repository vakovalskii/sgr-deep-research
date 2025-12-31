from __future__ import annotations

from pydantic import Field

from sgr_agent_core.base_tool import BaseTool


class ReasoningToolOWUI(BaseTool):
    """Special reasoning tool for Open-WebUI with clean field names.
    
    Agent core logic determines the next reasoning step with adaptive
    planning by schema-guided-reasoning capabilities. Keep all text fields
    concise and focused.

    Usage: Required tool. Use this tool before any other tool execution
    """
    
    # Override tool name to be clean for Open-WebUI
    tool_name: str = "reasoning"

    # Reasoning chain - step-by-step thinking process
    reasoning: str = Field(
        description="Brief step-by-step reasoning (2-3 sentences MAX)",
        max_length=400,
    )

    # Current state assessment
    current_situation: str = Field(
        description="Current situation assessment (2-3 sentences MAX)",
        max_length=300,
    )
    
    plan_status: str = Field(
        description="Status of current plan (1 sentence)",
        max_length=150,
    )
    
    enough_data: bool = Field(
        default=False,
        description="Sufficient data collected?",
    )

    # Next step planning
    next_step: str = Field(
        description="Next immediate action to take (1 sentence)",
        max_length=200,
    )
    
    remaining_steps: list[str] = Field(
        description="Remaining steps to complete (1-2 steps)",
        min_length=1,
        max_length=2,
        default_factory=lambda: ["Complete task"],
    )
    
    task_completed: bool = Field(
        description="Is the task finished?",
        default=False,
    )

    async def __call__(self, *args, **kwargs):
        return self.model_dump_json(indent=2)




