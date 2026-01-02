"""Agent definitions for research agents.

This module provides agent definitions that can be used to configure
research agents in the SGR Agent Core system.
"""

from pathlib import Path

import sgr_agent_core.tools as tools
from examples.sgr_deep_research.agents import (
    ResearchSGRAgent,
    ResearchSGRToolCallingAgent,
    ResearchToolCallingAgent,
)
from sgr_agent_core.agent_definition import AgentDefinition, PromptsConfig

DEFAULT_TOOLKIT = [
    tools.ClarificationTool,
    tools.GeneratePlanTool,
    tools.AdaptPlanTool,
    tools.FinalAnswerTool,
    tools.WebSearchTool,
    tools.ExtractPageContentTool,
    tools.CreateReportTool,
]


def get_research_agents_definitions() -> dict[str, AgentDefinition]:
    """Get research agent definitions.

    Returns:
        Dictionary of research agent definitions keyed by agent name
    """
    agents = [
        AgentDefinition(
            name="sgr_agent",
            base_class=ResearchSGRAgent,
            tools=DEFAULT_TOOLKIT,
            prompts=PromptsConfig(system_prompt_file=Path("sgr_agent_core/prompts/research_system_prompt.txt")),
        ),
        AgentDefinition(
            name="tool_calling_agent",
            base_class=ResearchToolCallingAgent,
            tools=DEFAULT_TOOLKIT,
            prompts=PromptsConfig(system_prompt_file=Path("sgr_agent_core/prompts/research_system_prompt.txt")),
        ),
        AgentDefinition(
            name="sgr_tool_calling_agent",
            base_class=ResearchSGRToolCallingAgent,
            tools=DEFAULT_TOOLKIT,
            prompts=PromptsConfig(system_prompt_file=Path("sgr_agent_core/prompts/research_system_prompt.txt")),
        ),
    ]
    return {agent.name: agent for agent in agents}
