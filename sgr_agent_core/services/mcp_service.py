import logging
from typing import Any, Type

from pydantic import create_model

from sgr_agent_core._optional import require
from sgr_agent_core.mcp_config import MCPConfig

logger = logging.getLogger(__name__)

_MCP_FEATURE = "Connecting to MCP servers"


class MCP2ToolConverter:
    @staticmethod
    def _to_CamelCase(name: str) -> str:
        return name.replace("_", " ").title().replace(" ", "")

    @staticmethod
    def _build_client(config: MCPConfig):
        """Build a fastmcp client from the core MCPConfig.

        fastmcp is an optional dependency, so it is imported here rather
        than at module scope; callers that never configure MCP servers
        never touch it.
        """
        fastmcp = require("fastmcp", feature=_MCP_FEATURE)
        FastMCPConfig = require("fastmcp.mcp_config", feature=_MCP_FEATURE).MCPConfig
        raw: dict[str, Any] = config if isinstance(config, dict) else config.model_dump(exclude_none=True)
        return fastmcp.Client(FastMCPConfig.model_validate(raw))

    @classmethod
    async def build_tools_from_mcp(cls, config: MCPConfig):
        from sgr_agent_core import BaseTool, MCPBaseTool

        tools = []
        if not config.mcpServers:
            return tools

        SchemaConverter = require("jambo", feature=_MCP_FEATURE).SchemaConverter
        client = cls._build_client(config)
        async with client:
            mcp_tools = await client.list_tools()

            for t in mcp_tools:
                if not t.name or not t.inputSchema:
                    logger.error(f"Skipping tool due to missing name or input schema: {t}")
                    continue

                try:
                    t.inputSchema["title"] = cls._to_CamelCase(t.name)
                    PdModel = SchemaConverter.build(t.inputSchema)
                except Exception as e:
                    logger.error(f"Error creating model {t.name} from schema: {t.inputSchema}: {e}")
                    continue

                ToolCls: Type[BaseTool] = create_model(
                    f"MCP{cls._to_CamelCase(t.name)}", __base__=(PdModel, MCPBaseTool), __doc__=t.description or ""
                )
                ToolCls.tool_name = t.name
                ToolCls.description = t.description or ""
                ToolCls._client = client
                tools.append(ToolCls)
                logger.info(f"Built MCP Tool: {ToolCls.tool_name}")

            logger.info(f"Built {len(tools)} MCP tools.")
            return tools
