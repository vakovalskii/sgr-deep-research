from __future__ import annotations

import logging
import operator
from abc import ABC
from functools import reduce
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Type, TypeVar

from pydantic import BaseModel, Field, create_model

from sgr_deep_research.core.models import AgentStatesEnum
from sgr_deep_research.settings import get_config

if TYPE_CHECKING:
    from sgr_deep_research.core.models import ResearchContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
config = get_config()


class BaseTool(BaseModel):
    """Class to provide tool handling capabilities."""

    tool_name: ClassVar[str] = None
    description: ClassVar[str] = None

    def __call__(self, context: ResearchContext) -> str:
        """Result should be a string or dumped json."""
        raise NotImplementedError("Execute method must be implemented by subclass")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.tool_name = cls.tool_name or cls.__name__.lower()
        cls.description = cls.description or cls.__doc__ or ""


class ClarificationTool(BaseTool):
    """Ask clarifying questions when facing ambiguous request."""

    reasoning: str = Field(description="Why clarification is needed")
    unclear_terms: list[str] = Field(description="List of unclear terms or concepts", min_length=1, max_length=5)
    assumptions: list[str] = Field(description="Possible interpretations to verify", min_length=2, max_length=4)
    questions: list[str] = Field(description="3-5 specific clarifying questions", min_length=3, max_length=5)

    def __call__(self, context: ResearchContext) -> str:
        return "\n".join(self.questions)


class GeneratePlanTool(BaseTool):
    """Generate research plan.

    Useful to split complex request into manageable steps.
    """

    reasoning: str = Field(description="Justification for research approach")
    research_goal: str = Field(description="Primary research objective")
    planned_steps: list[str] = Field(description="List of 3-4 planned steps", min_length=3, max_length=4)
    search_strategies: list[str] = Field(description="Information search strategies", min_length=2, max_length=3)

    def __call__(self, context: ResearchContext) -> str:
        return self.model_dump_json(
            indent=2,
            exclude={
                "reasoning",
            },
        )


class AdaptPlanTool(BaseTool):
    """Adapt research plan based on new findings."""

    reasoning: str = Field(description="Why plan needs adaptation based on new data")
    original_goal: str = Field(description="Original research goal")
    new_goal: str = Field(description="Updated research goal")
    plan_changes: list[str] = Field(description="Specific changes made to plan", min_length=1, max_length=3)
    next_steps: list[str] = Field(description="Updated remaining steps", min_length=2, max_length=4)

    def __call__(self, context: ResearchContext) -> str:
        return self.model_dump_json(
            indent=2,
            exclude={
                "reasoning",
            },
        )


class AgentCompletionTool(BaseTool):
    """Finalize research task and complete agent execution after all steps are
    completed."""

    reasoning: str = Field(description="Why task is now complete")
    completed_steps: list[str] = Field(description="Summary of completed steps", min_length=1, max_length=5)
    status: Literal[AgentStatesEnum.COMPLETED, AgentStatesEnum.FAILED] = Field(description="Task completion status")

    def __call__(self, context: ResearchContext) -> str:
        context.state = self.status
        return self.model_dump_json(
            indent=2,
        )


class ReasoningTool(BaseTool):
    """Agent Core - Determines next reasoning step with adaptive planning"""

    # Reasoning chain - step-by-step thinking process (helps stabilize model)
    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning process leading to decision", min_length=2, max_length=4
    )

    # Reasoning and state assessment
    current_situation: str = Field(description="Current research situation analysis")
    plan_status: str = Field(description="Status of current plan execution")
    previous_search_summary: str = Field(
        default="",
        description="Summary of key findings from previous searches (to maintain context without full search results)"
    )
    enough_data: bool = Field(
        default=False,
        description="Sufficient data collected for comprehensive report?",
    )

    # Next step planning
    remaining_steps: list[str] = Field(description="1-3 remaining steps to complete task", min_length=1, max_length=3)
    task_completed: bool = Field(description="Is the research task finished?")

    def __call__(self, *args, **kwargs):
        return self.model_dump_json(
            indent=2,
        )


T = TypeVar("T", bound=BaseTool)


class NextStepToolStub(ReasoningTool, ABC):
    """SGR Core - Determines next reasoning step with adaptive planning, choosing appropriate tool
    (!) Stub class for correct autocomplete. Use NextStepToolsBuilder"""

    function: T = Field(description="Select the appropriate tool for the next step")


class NextStepToolsBuilder:
    """SGR Core - Builder for NextStepTool with dynamic union tool function type on
    pydantic models level."""

    @classmethod
    def _create_discriminant_tool(cls, tool_class: Type[T]) -> Type[BaseModel]:
        """Create discriminant version of tool with tool_name as instance
        field."""
        tool_name = tool_class.tool_name

        discriminant_tool = create_model(
            f"{tool_class.__name__}WithDiscriminant",
            __base__=tool_class,
            tool_name_discriminator=(
                Literal[tool_name],  # noqa
                Field(default=tool_name, description="Tool name discriminator"),
            ),
        )
        discriminant_tool.__call__ = tool_class.__call__

        return discriminant_tool

    @classmethod
    def _create_tool_types_union(cls, tools_list: list[Type[T]]) -> Type:
        """Create discriminated union of tools."""
        if len(tools_list) == 1:
            return cls._create_discriminant_tool(tools_list[0])
        # SGR inference struggles with choosing right schema otherwise
        discriminant_tools = [cls._create_discriminant_tool(tool) for tool in tools_list]
        union = reduce(operator.or_, discriminant_tools)
        return Annotated[union, Field()]

    @classmethod
    def build_NextStepTools(cls, tools_list: list[Type[T]]) -> Type[NextStepToolStub]:  # noqa
        return create_model(
            "NextStepTools",
            __base__=NextStepToolStub,
            function=(cls._create_tool_types_union(tools_list), Field()),
        )


system_agent_tools = [
    # ClarificationTool,  # Disabled - agents should not ask clarifications
    GeneratePlanTool,
    AdaptPlanTool,
    AgentCompletionTool,
    ReasoningTool,
]
