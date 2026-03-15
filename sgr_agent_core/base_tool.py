from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, ClassVar, Self

from fastmcp import Client
from pydantic import BaseModel

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.services.registry import ToolRegistry

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)


class ToolRegistryMixin:
    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__name__ not in ("BaseTool", "MCPBaseTool", "SystemBaseTool"):
            ToolRegistry.register(cls, name=cls.tool_name)


class BaseTool(BaseModel, ToolRegistryMixin):
    """Class to provide tool handling capabilities."""

    tool_name: ClassVar[str] = None
    description: ClassVar[str] = None
    isSystemTool: ClassVar[bool] = False
    # Optional: Pydantic model for this tool's config; agent.get_tool_config(tool_class) returns it
    config_model: ClassVar[type[BaseModel] | None] = None
    # If set, agent config attribute to merge as base (e.g. "search") when resolving tool config
    base_config_attr: ClassVar[str | None] = None

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs) -> str:
        """The result should be a string or dumped JSON."""
        raise NotImplementedError("Execute method must be implemented by subclass")

    def __init_subclass__(cls, **kwargs) -> None:
        if "tool_name" not in cls.__dict__:
            cls.tool_name = cls.__name__.lower()
        if "description" not in cls.__dict__:
            cls.description = cls.__doc__ or ""
        super().__init_subclass__(**kwargs)


class SystemBaseTool(BaseTool):
    """Base class for system tools that are always available and never
    filtered."""

    isSystemTool: ClassVar[bool] = True


class MCPBaseTool(BaseTool):
    """Base model for MCP Tool schema."""

    _client: ClassVar[Client | None] = None

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs) -> str:
        config = GlobalConfig()
        payload = self.model_dump(mode="json")
        try:
            async with self._client:
                result = await self._client.call_tool(self.tool_name, payload)
                return json.dumps([m.model_dump_json() for m in result.content], ensure_ascii=False)[
                    : config.execution.mcp_context_limit
                ]
        except Exception as e:
            logger.error(f"Error processing MCP tool {self.tool_name}: {e}")
            return f"Error: {e}"

    @classmethod
    def model_validate_json(cls, json_data: str | bytes | bytearray, **kwargs) -> Self:
        return super().model_validate_json(json_data=json_data or "{}", **kwargs)
