"""
SGR Agent Core - Schema-Guided Reasoning for building agentic systems

A powerful research assistant that combines structured reasoning with deep analysis capabilities.
"""

# Version info — derived from the installed package metadata,
# which setuptools-scm populates from the latest git tag at build time.
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("sgr-agent-core")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"

__author__ = "sgr-agent-core-team"

# Base classes (from direct .py files)
from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_definition import (
    AgentConfig,
    AgentDefinition,
    ExecutionConfig,
    LLMConfig,
    PromptsConfig,
)
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import *  # noqa: F403
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.base_tool import BaseTool, MCPBaseTool, SystemBaseTool
from sgr_agent_core.mcp_config import MCPConfig
from sgr_agent_core.models import (
    AgentContext,
    AgentStatesEnum,
    AgentStatistics,
    SearchResult,
    SourceData,
)
from sgr_agent_core.next_step_tool import NextStepToolsBuilder, NextStepToolStub
from sgr_agent_core.services import (
    AgentRegistry,
    MCP2ToolConverter,
    PromptLoader,
    ToolRegistry,
)
from sgr_agent_core.skills import (
    BaseSkill,
    SkillError,
    SkillLoader,
    SkillMetadata,
    SkillRegistry,
    SkillsConfig,
)
from sgr_agent_core.tools import *  # noqa: F403

__all__ = [
    # Version
    "__version__",
    "__author__",
    # Base classes
    "BaseAgent",
    "BaseTool",
    "SystemBaseTool",
    "MCPBaseTool",
    # Models
    "AgentStatesEnum",
    "AgentStatistics",
    "AgentContext",
    "SearchResult",
    "SourceData",
    # Services
    "AgentRegistry",
    "MCP2ToolConverter",
    "PromptLoader",
    "ToolRegistry",
    # Configuration
    "AgentConfig",
    "AgentDefinition",
    "LLMConfig",
    "PromptsConfig",
    "ExecutionConfig",
    "GlobalConfig",
    "MCPConfig",
    # Next step tools
    "NextStepToolStub",
    "NextStepToolsBuilder",
    # Factory
    "AgentFactory",
    # Skills
    "BaseSkill",
    "SkillMetadata",
    "SkillLoader",
    "SkillRegistry",
    "SkillsConfig",
    "SkillError",
]
