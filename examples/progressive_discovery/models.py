from pydantic import Field

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import AgentContext


class ProgressiveDiscoveryContext(AgentContext):
    """Extended agent context for progressive discovery.

    Inherits all standard AgentContext fields (iteration, state,
    searches, etc.) and adds tool lists used by the discovery mechanism.
    """

    all_tools: list[type[BaseTool]] = Field(
        default_factory=list, description="Full list of non-system tools available for discovery"
    )
    discovered_tools: list[type[BaseTool]] = Field(
        default_factory=list, description="Tools discovered so far via SearchToolsTool"
    )
