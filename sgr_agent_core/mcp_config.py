"""Lightweight MCP server configuration.

Mirrors the shape of ``fastmcp.mcp_config.MCPConfig`` without importing
fastmcp, so ``AgentConfig.mcp`` can stay a plain field in the core package.
``MCP2ToolConverter`` converts an instance of this model into the fastmcp one
when MCP servers are actually configured — see
:mod:`sgr_agent_core.services.mcp_service`.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class MCPConfig(BaseModel, extra="allow"):
    """Configuration for MCP servers in the canonical MCP format.

    Server entries are kept as raw dictionaries; fastmcp validates them
    into its own transport-specific models when a client is built.
    Unknown top-level keys are preserved so fastmcp-specific extensions
    pass through.
    """

    mcpServers: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def wrap_servers_at_root(cls, values: Any) -> Any:
        """If there's no mcpServers key but there are server configs at root,
        wrap them."""
        if not isinstance(values, dict) or "mcpServers" in values:
            return values
        has_servers = any(isinstance(v, dict) and ("command" in v or "url" in v) for v in values.values())
        if has_servers:
            return {"mcpServers": values}
        return values

    def add_server(self, name: str, server: Any) -> None:
        """Add or update a server in the configuration."""
        self.mcpServers[name] = server

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> Self:
        """Parse MCP configuration from dictionary format."""
        return cls.model_validate(config)

    def to_dict(self) -> dict[str, Any]:
        """Convert MCPConfig to dictionary format, preserving all fields."""
        return self.model_dump(exclude_none=True)
