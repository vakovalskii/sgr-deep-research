"""Agent Factory for dynamic agent creation from definitions."""

import logging
from typing import Any, Type, TypeVar

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_definition import AgentDefinition, LLMConfig, ToolDefinition
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.services import AgentRegistry, MCP2ToolConverter, StreamingGeneratorRegistry
from sgr_agent_core.stream import OpenAIStreamingGenerator

logger = logging.getLogger(__name__)

Agent = TypeVar("Agent", bound=BaseAgent)


class AgentFactory:
    """Factory for creating agent instances from definitions.

    Use AgentRegistry and ToolRegistry to look up agent classes by name
    and create instances with the appropriate configuration.
    """

    @classmethod
    def _create_client(cls, llm_config: LLMConfig) -> AsyncOpenAI:
        """Create OpenAI client from configuration.

        Args:
            llm_config: LLM configuration

        Returns:
            Configured AsyncOpenAI client
        """
        client_kwargs = {"base_url": llm_config.base_url, "api_key": llm_config.api_key}
        if llm_config.proxy:
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=llm_config.proxy)

        return AsyncOpenAI(**client_kwargs)

    @classmethod
    def _resolve_streaming_generator(cls, name: str) -> type[OpenAIStreamingGenerator]:
        """Resolve streaming generator class from registry by name.

        Args:
            name: Value from execution.streaming_generator (e.g. 'openai', 'open_webui')

        Returns:
            Streaming generator class

        Raises:
            ValueError: If streaming generator not found
        """
        generator_class = StreamingGeneratorRegistry.get(name)
        if generator_class is None:
            raise ValueError(
                f"Streaming generator '{name}' not found. "
                f"Available: {', '.join([c.__name__ for c in StreamingGeneratorRegistry.list_items()])}"
            )
        return generator_class

    @classmethod
    def _resolve_tools_with_configs(
        cls,
        tool_defs: list[ToolDefinition],
    ) -> tuple[list[type[BaseTool]], dict[str, dict[str, Any]]]:
        """Build toolkit and tool_configs from ToolDefinition objects.

        Args:
            tool_defs: List of ToolDefinition objects from AgentDefinition

        Returns:
            Tuple of (toolkit, tool_configs) where toolkit is a list of tool classes
            and tool_configs maps tool_name to its kwargs
        """
        toolkit: list[type[BaseTool]] = []
        tool_configs: dict[str, dict[str, Any]] = {}
        for tool_def in tool_defs:
            tool_class = tool_def.base_class
            toolkit.append(tool_class)
            tool_configs[tool_class.tool_name] = tool_def.tool_kwargs()
        return toolkit, tool_configs

    @classmethod
    async def create(cls, agent_def: AgentDefinition, task_messages: list[ChatCompletionMessageParam]) -> Agent:
        """Create an agent instance from a definition.

        Args:
            agent_def: Agent definition with configuration (classes already resolved)
            task_messages: Task messages in OpenAI ChatCompletionMessageParam format

        Returns:
            Created agent instance

        Raises:
            ValueError: If agent creation fails
        """
        # Resolve base_class
        # Can be:
        # 1. Class object (already resolved by Pydantic ImportString, or passed directly)
        # 2. String - registry name to look up
        # Note: ImportString from Pydantic is already resolved to class by this point
        BaseClass: Type[Agent] | None = None

        if isinstance(agent_def.base_class, type):
            # Already a class (either passed directly or resolved from ImportString by Pydantic)
            BaseClass = agent_def.base_class
        elif isinstance(agent_def.base_class, str):
            # String - look up in registry
            BaseClass = AgentRegistry.get(agent_def.base_class)

        if BaseClass is None:
            error_msg = (
                f"Agent base class '{agent_def.base_class}' not found.\n"
                f"Available base classes in registry: {', '.join([c.__name__ for c in AgentRegistry.list_items()])}\n"
                f"To fix this issue:\n"
                f"  - Check that '{agent_def.base_class}' is spelled correctly in your configuration\n"
                f"  - If using class name, ensure the custom agent classes are imported before creating agents "
                f"(otherwise they won't be registered)\n"
                f"  - If using import string (e.g., 'sgr_file_agent.SGRFileAgent'), ensure the module is imported "
                f"and the class is registered in AgentRegistry"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        mcp_tools: list = await MCP2ToolConverter.build_tools_from_mcp(agent_def.mcp)
        tools, tool_configs = cls._resolve_tools_with_configs(agent_def.tools)
        tools.extend(mcp_tools)

        try:
            # Extract agent-specific parameters from agent_def (e.g., working_directory)
            # These are fields that are not part of standard AgentConfig but are allowed via extra="allow"
            agent_kwargs = {}
            for key, value in agent_def.model_dump().items():
                agent_kwargs[key] = value

            agent = BaseClass(
                task_messages=task_messages,
                def_name=agent_def.name,
                toolkit=tools,
                tool_configs=tool_configs,
                openai_client=cls._create_client(agent_def.llm),
                agent_config=agent_def,
                streaming_generator=cls._resolve_streaming_generator(agent_def.execution.streaming_generator),
                **agent_kwargs,
            )
            logger.info(
                f"Created agent '{agent_def.name}' "
                f"using base class '{BaseClass.__name__}' "
                f"with {len(agent.toolkit)} tools"
            )
            return agent
        except Exception as e:
            logger.error(f"Failed to create agent '{agent_def.name}': {e}", exc_info=True)
            raise ValueError(f"Failed to create agent: {e}") from e

    @classmethod
    def get_definitions_list(cls) -> list[AgentDefinition]:
        """Get all agent definitions from config.

        Returns:
            List of agent definitions from config
        """
        config = GlobalConfig()
        return list(config.agents.values())
