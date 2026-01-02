"""
SGR Agent Core - Schema-Guided Reasoning for building agentic systems

A powerful research assistant that combines structured reasoning with deep analysis capabilities.
"""

# Version info
__version__ = "0.5.1"
__author__ = "sgr-agent-core-team"

# Base classes (from direct .py files)
from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_definition import (
    AgentConfig,
    AgentDefinition,
    ExecutionConfig,
    LLMConfig,
    PromptsConfig,
    SearchConfig,
)
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import *  # noqa: F403
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.base_tool import BaseTool, MCPBaseTool
from sgr_agent_core.models import (
    AgentContext,
    AgentStatesEnum,
    AgentStatistics,
    SearchResult,
    SourceData,
)
from sgr_agent_core.next_step_tool import NextStepToolsBuilder, NextStepToolStub
from sgr_agent_core.services import AgentRegistry, MCP2ToolConverter, PromptLoader, ToolRegistry
from sgr_agent_core.tools import *  # noqa: F403

__all__ = [
    # Version
    "__version__",
    "__author__",
    # Base classes
    "BaseAgent",
    "BaseTool",
    "MCPBaseTool",
    # Models
    "AgentStatesEnum",
    "AgentStatistics",
    "AgentContext",
    "SearchResult",
    "SourceData",
    # Services
    "AgentRegistry",
    "ToolRegistry",
    "PromptLoader",
    "MCP2ToolConverter",
    # Configuration
    "AgentConfig",
    "AgentDefinition",
    "LLMConfig",
    "PromptsConfig",
    "SearchConfig",
    "ExecutionConfig",
    "GlobalConfig",
    # Next step tools
    "NextStepToolStub",
    "NextStepToolsBuilder",
    # Models
    "AgentStatesEnum",
    "AgentContext",
    "SearchResult",
    "SourceData",
    # Factory
    "AgentFactory",
]
