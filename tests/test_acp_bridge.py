"""Tests for Agent Client Protocol (ACP) stdio bridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from acp.schema import TextContentBlock

from sgr_agent_core.agent_definition import AgentDefinition, ExecutionConfig, LLMConfig, PromptsConfig
from sgr_agent_core.agents import SGRAgent
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.stream import BaseStreamingGenerator


@pytest.mark.asyncio
async def test_acp_extract_prompt_text_joins_text_blocks():
    """Prompt extraction should concatenate text parts from ACP content blocks."""
    from sgr_agent_core.acp.bridge import extract_prompt_text

    blocks = [
        TextContentBlock(type="text", text="Hello "),
        TextContentBlock(type="text", text="world"),
    ]
    assert extract_prompt_text(blocks) == "Hello world"


@pytest.mark.asyncio
async def test_acp_bridge_initialize_returns_agent_info():
    """initialize should negotiate protocol version and return agent capabilities."""
    from sgr_agent_core.acp.bridge import SGRACPBridge

    bridge = SGRACPBridge(default_agent_name="sgr_agent")
    resp = await bridge.initialize(protocol_version=1, client_capabilities=None, client_info=None)
    assert resp.protocol_version == 1
    assert resp.agent_info.name == "sgr-agent-core"
    assert resp.agent_capabilities.load_session is False


@pytest.mark.asyncio
async def test_acp_bridge_new_session_returns_session_id():
    """new_session should create a session with a stable id prefix pattern."""
    from sgr_agent_core.acp.bridge import SGRACPBridge

    bridge = SGRACPBridge(default_agent_name="sgr_agent")
    out = await bridge.new_session(cwd="/tmp", mcp_servers=None)
    assert out.session_id.startswith("sgr_")


@pytest.mark.asyncio
async def test_agent_factory_create_accepts_streaming_generator_override():
    """AgentFactory.create should allow overriding streaming generator class."""
    from tests.test_agent_factory import mock_global_config

    class DummyGen(BaseStreamingGenerator):
        name = "dummy_acp_test"

        def __init__(self, agent_id: str) -> None:
            super().__init__()
            self.agent_id = agent_id

    with (
        patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
        mock_global_config(),
    ):
        agent_def = AgentDefinition(
            name="sgr_agent",
            base_class=SGRAgent,
            tools=["reasoningtool"],
            llm=LLMConfig(api_key="k", base_url="https://api.openai.com/v1"),
            prompts=PromptsConfig(
                system_prompt_str="s",
                initial_user_request_str="i",
                clarification_response_str="c",
            ),
            execution=ExecutionConfig(streaming_generator="openai"),
        )

        agent = await AgentFactory.create(
            agent_def,
            [{"role": "user", "content": "x"}],
            streaming_generator=DummyGen,
        )

    assert isinstance(agent.streaming_generator, DummyGen)
