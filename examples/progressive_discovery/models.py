from pydantic import BaseModel, Field

from sgr_agent_core.base_tool import BaseTool


class ProgressiveDiscoveryContext(BaseModel):
    """Typed context for progressive discovery agent.

    Stores tool lists used by the discovery mechanism instead of raw
    dict access on custom_context.
    """

    model_config = {"arbitrary_types_allowed": True}

    all_tools: list[type[BaseTool]] = Field(
        default_factory=list, description="Full list of non-system tools available for discovery"
    )
    discovered_tools: list[type[BaseTool]] = Field(
        default_factory=list, description="Tools discovered so far via SearchToolsTool"
    )
