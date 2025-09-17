import uuid
from typing import Literal, Type

from sgr_deep_research.core.agents.sgr_tools_agent import SGRToolCallingResearchAgent
from sgr_deep_research.core.tools import BaseTool


class SGRAutoToolCallingResearchAgent(SGRToolCallingResearchAgent):
    """SGR Tool Calling Research Agent variation for benchmark with automatic
    tool selection."""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        # max_clarifications: int = 3,  # Disabled - agent should not ask clarifications
        max_searches: int = 3,  # Aligned with config.search.max_results
        max_iterations: int | None = None,
    ):
        super().__init__(task, toolkit, max_searches, max_iterations)
        self.id = f"sgr_auto_tool_calling_agent_{uuid.uuid4()}"
        self.tool_choice: Literal["auto"] = "auto"
