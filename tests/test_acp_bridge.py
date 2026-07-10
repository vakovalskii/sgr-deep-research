"""Tests for Agent Client Protocol (ACP) stdio bridge."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from acp.schema import TextContentBlock

from sgr_agent_core.agent_definition import AgentDefinition, ExecutionConfig, LLMConfig, PromptsConfig
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import SGRAgent
from sgr_agent_core.stream import BaseStreamingGenerator


def _fake_bridge_config(agent_models, acp_agent=None, acp_models=None):
    """Minimal GlobalConfig stand-in exposing the attributes the bridge reads."""
    agents = {name: SimpleNamespace(llm=SimpleNamespace(model=model)) for name, model in agent_models.items()}
    acp = SimpleNamespace(agent=acp_agent, models=list(acp_models or []))
    return SimpleNamespace(agents=agents, acp=acp)


@contextmanager
def _patch_bridge_config(cfg):
    """Patch the GlobalConfig reference used inside the ACP bridge module."""
    with patch("sgr_agent_core.acp.bridge.GlobalConfig", return_value=cfg):
        yield


@pytest.mark.asyncio
async def test_acp_extract_prompt_text_joins_text_blocks():
    """Prompt extraction should concatenate text parts from ACP content
    blocks."""
    from sgr_agent_core.acp.bridge import extract_prompt_text

    blocks = [
        TextContentBlock(type="text", text="Hello "),
        TextContentBlock(type="text", text="world"),
    ]
    assert extract_prompt_text(blocks) == "Hello world"


@pytest.mark.asyncio
async def test_acp_bridge_initialize_returns_agent_info():
    """Initialize should negotiate protocol version and return agent
    capabilities."""
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

    cfg = _fake_bridge_config({"sgr_agent": "gpt-4o-mini"})
    bridge = SGRACPBridge(default_agent_name="sgr_agent")
    with _patch_bridge_config(cfg):
        out = await bridge.new_session(cwd="/tmp", mcp_servers=None)
    assert out.session_id.startswith("sgr_")


@pytest.mark.asyncio
async def test_acp_new_session_advertises_agent_and_model_options():
    """new_session should expose 'agent' and 'model' selectors so the user can
    switch them at runtime."""
    from sgr_agent_core.acp.bridge import SGRACPBridge

    cfg = _fake_bridge_config(
        {"sgr_agent": "gpt-4o-mini", "tool_calling_agent": "gpt-4o"},
        acp_agent="sgr_agent",
        acp_models=["o3-mini"],
    )
    bridge = SGRACPBridge()
    with _patch_bridge_config(cfg):
        out = await bridge.new_session(cwd="/tmp", mcp_servers=None)

    options = {opt.id: opt for opt in out.config_options}
    assert set(options) == {"agent", "model"}

    agent_opt = options["agent"]
    assert agent_opt.category == "_agent"
    assert agent_opt.current_value == "sgr_agent"
    assert [o.value for o in agent_opt.options] == ["sgr_agent", "tool_calling_agent"]

    model_opt = options["model"]
    assert model_opt.category == "model"
    assert model_opt.current_value == "gpt-4o-mini"
    # acp.models first, then each agent's declared model, de-duplicated
    assert [o.value for o in model_opt.options] == ["o3-mini", "gpt-4o-mini", "gpt-4o"]


@pytest.mark.asyncio
async def test_acp_set_config_option_switches_agent():
    """Setting the 'agent' option should update the session and echo the full
    config state."""
    from sgr_agent_core.acp.bridge import SGRACPBridge

    cfg = _fake_bridge_config(
        {"sgr_agent": "gpt-4o-mini", "tool_calling_agent": "gpt-4o"},
        acp_agent="sgr_agent",
    )
    bridge = SGRACPBridge()
    with _patch_bridge_config(cfg):
        out = await bridge.new_session(cwd="/tmp", mcp_servers=None)
        resp = await bridge.set_config_option(
            config_id="agent", session_id=out.session_id, value="tool_calling_agent"
        )

    assert bridge._sessions[out.session_id].agent_name == "tool_calling_agent"
    agent_opt = {opt.id: opt for opt in resp.config_options}["agent"]
    assert agent_opt.current_value == "tool_calling_agent"


@pytest.mark.asyncio
async def test_acp_set_config_option_switches_model():
    """Setting the 'model' option should update the session's model."""
    from sgr_agent_core.acp.bridge import SGRACPBridge

    cfg = _fake_bridge_config({"sgr_agent": "gpt-4o-mini"}, acp_agent="sgr_agent", acp_models=["o3-mini"])
    bridge = SGRACPBridge()
    with _patch_bridge_config(cfg):
        out = await bridge.new_session(cwd="/tmp", mcp_servers=None)
        resp = await bridge.set_config_option(config_id="model", session_id=out.session_id, value="o3-mini")

    assert bridge._sessions[out.session_id].model == "o3-mini"
    model_opt = {opt.id: opt for opt in resp.config_options}["model"]
    assert model_opt.current_value == "o3-mini"


@pytest.mark.asyncio
async def test_acp_set_config_option_rejects_unknown_value():
    """Unknown agent/model values should be rejected."""
    from sgr_agent_core.acp.bridge import SGRACPBridge

    cfg = _fake_bridge_config({"sgr_agent": "gpt-4o-mini"}, acp_agent="sgr_agent")
    bridge = SGRACPBridge()
    with _patch_bridge_config(cfg):
        out = await bridge.new_session(cwd="/tmp", mcp_servers=None)
        with pytest.raises(ValueError):
            await bridge.set_config_option(config_id="model", session_id=out.session_id, value="nope")
        with pytest.raises(ValueError):
            await bridge.set_config_option(config_id="agent", session_id=out.session_id, value="nope")


@pytest.mark.asyncio
async def test_acp_session_applies_model_override_to_agent_definition():
    """The session's selected model should override the agent definition's
    model when a turn is built, without mutating the shared definition."""
    from sgr_agent_core.acp.bridge import SGRACPBridge
    from tests.test_agent_factory import mock_global_config

    with mock_global_config():
        agent_def = AgentDefinition(
            name="sgr_agent",
            base_class=SGRAgent,
            tools=["reasoningtool"],
            llm=LLMConfig(api_key="k", base_url="https://api.openai.com/v1", model="gpt-4o-mini"),
            prompts=PromptsConfig(
                system_prompt_str="s",
                initial_user_request_str="i",
                clarification_response_str="c",
            ),
            execution=ExecutionConfig(streaming_generator="openai"),
        )

    cfg = SimpleNamespace(agents={"sgr_agent": agent_def}, acp=SimpleNamespace(agent="sgr_agent", models=["o3-mini"]))
    bridge = SGRACPBridge()
    with _patch_bridge_config(cfg):
        out = await bridge.new_session(cwd="/tmp", mcp_servers=None)
        await bridge.set_config_option(config_id="model", session_id=out.session_id, value="o3-mini")
        resolved = bridge._agent_definition_for_session(bridge._sessions[out.session_id])

    assert resolved.llm.model == "o3-mini"
    # Original definition must stay untouched
    assert agent_def.llm.model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_agent_factory_create_accepts_streaming_generator_override():
    """AgentFactory.create should allow overriding streaming generator
    class."""
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
