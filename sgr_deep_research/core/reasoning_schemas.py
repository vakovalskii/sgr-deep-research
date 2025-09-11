from typing import Literal

from pydantic import BaseModel, Field, field_validator

from sgr_deep_research.core.prompts import PromptLoader


class ToolBase(BaseModel):
    """Base model adding tolerant 'tool' normalization for provider quirks.

    Normalizes values like 'GeneratePlan' (PascalCase) -> 'generate_plan' (snake_case)
    before Literal validation. This helps with providers that change casing.
    """

    @field_validator("tool", mode="before", check_fields=False)
    @classmethod
    def _normalize_tool(cls, v):
        if isinstance(v, str):
            normalized = "".join(["_" + c.lower() if c.isupper() else c for c in v]).lstrip("_")
            return normalized
        return v


class Clarification(ToolBase):
    """Ask clarifying questions when facing ambiguous requests."""

    tool: Literal["clarification"]
    reasoning: str = Field(description="Why clarification is needed")
    unclear_terms: list[str] = Field(description="List of unclear terms or concepts", min_length=1, max_length=5)
    assumptions: list[str] = Field(description="Possible interpretations to verify", min_length=2, max_length=4)
    questions: list[str] = Field(description="3-5 specific clarifying questions", min_length=3, max_length=5)


class GeneratePlan(ToolBase):
    """Generate research plan based on clear user request."""

    tool: Literal["generate_plan"]
    reasoning: str = Field(description="Justification for research approach")
    research_goal: str = Field(description="Primary research objective")
    planned_steps: list[str] = Field(description="List of 3-4 planned steps", min_length=3, max_length=4)
    search_strategies: list[str] = Field(description="Information search strategies", min_length=2, max_length=3)


class WebSearch(ToolBase):
    """Search for information with credibility focus."""

    tool: Literal["web_search"]
    reasoning: str = Field(description="Why this search is needed and what to expect")
    query: str = Field(description="Search query in same language as user request")
    max_results: int = Field(default=10, description="Maximum results", ge=1, le=10)
    plan_adapted: bool = Field(default=False, description="Is this search after plan adaptation?")
    scrape_content: bool = Field(
        default=False,
        description="Fetch full page content for deeper analysis",
    )


class AdaptPlan(ToolBase):
    """Adapt research plan based on new findings."""

    tool: Literal["adapt_plan"]
    reasoning: str = Field(description="Why plan needs adaptation based on new data")
    original_goal: str = Field(description="Original research goal")
    new_goal: str = Field(description="Updated research goal")
    plan_changes: list[str] = Field(description="Specific changes made to plan", min_length=1, max_length=3)
    next_steps: list[str] = Field(description="Updated remaining steps", min_length=2, max_length=4)


class CreateReport(ToolBase):
    """Create comprehensive research report with citations."""

    tool: Literal["create_report"]
    reasoning: str = Field(description="Why ready to create report now")
    title: str = Field(description="Report title")
    user_request_language_reference: str = Field(
        description="Copy of original user request to ensure language consistency"
    )
    content: str = Field(
        description="Write comprehensive research report following the REPORT CREATION GUIDELINES from system prompt. "
        "Use the SAME LANGUAGE as user_request_language_reference."
    )
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in findings")


class ReportCompletion(ToolBase):
    """Complete research task."""

    tool: Literal["report_completion"]
    reasoning: str = Field(description="Why research is now complete")
    completed_steps: list[str] = Field(description="Summary of completed steps", min_length=1, max_length=5)
    status: Literal["completed", "failed"] = Field(description="Task completion status")


# =============================================================================
# MAIN SGR SCHEMA - Adaptive Reasoning Core
# =============================================================================


class NextStep(BaseModel):
    """SGR Core - Determines next reasoning step with adaptive planning"""

    # Reasoning chain - step-by-step thinking process (helps stabilize model)
    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning process leading to decision", min_length=2, max_length=4
    )

    # Reasoning and state assessment
    current_situation: str = Field(description="Current research situation analysis")
    plan_status: str = Field(description="Status of current plan execution")
    enough_data: bool = Field(
        default=False,
        description="Sufficient data collected for comprehensive report?",
    )

    # Next step planning
    remaining_steps: list[str] = Field(description="1-3 remaining steps to complete task", min_length=1, max_length=3)
    task_completed: bool = Field(description="Is the research task finished?")

    # Tool routing with clarification-first bias
    function: (
        Clarification  # FIRST PRIORITY: When uncertain
        | GeneratePlan  # SECOND: When request is clear
        | WebSearch  # Core research tool
        | AdaptPlan  # When findings conflict with plan
        | CreateReport  # When sufficient data collected
        | ReportCompletion  # Task completion
    ) = Field(description=PromptLoader.get_tool_function_prompt())
