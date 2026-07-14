"""Tests for exposing skills as ACP available_commands (Layer 5)."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from acp.schema import AvailableCommandsUpdate

from sgr_agent_core.acp.bridge import SGRACPBridge
from sgr_agent_core.skills import Skill, SkillMetadata


def _skill(name, description="A skill.", body="BODY", **kw):
    return Skill(metadata=SkillMetadata(name=name, description=description, **kw), body=body)


def _fake_cfg(agent_models):
    agents = {name: SimpleNamespace(llm=SimpleNamespace(model=m), skills=None) for name, m in agent_models.items()}
    return SimpleNamespace(agents=agents, acp=SimpleNamespace(agent=next(iter(agent_models)), models=[]))


@contextmanager
def _patch_cfg(cfg):
    with patch("sgr_agent_core.acp.bridge.GlobalConfig", return_value=cfg):
        yield


class TestAcpCommandBuilding:
    def test_build_available_commands_from_skills(self):
        bridge = SGRACPBridge()
        cmds = bridge._build_available_commands([_skill("greet", "Greets people.")])
        assert [c.name for c in cmds] == ["greet"]
        assert cmds[0].description == "Greets people."

    def test_non_user_invocable_excluded(self):
        bridge = SGRACPBridge()
        cmds = bridge._build_available_commands(
            [_skill("shown", "Shown."), _skill("hidden", "Hidden.", user_invocable=False)]
        )
        assert [c.name for c in cmds] == ["shown"]


class TestAcpSlashCommandExpansion:
    def test_expand_matching_command(self):
        bridge = SGRACPBridge()
        skills = [_skill("greet", body="Greet the user warmly.")]
        expanded = bridge._expand_skill_command("/greet say hi to Bob", skills)
        assert expanded is not None
        assert "Greet the user warmly." in expanded
        assert "say hi to Bob" in expanded

    def test_expand_unknown_command_returns_none(self):
        bridge = SGRACPBridge()
        assert bridge._expand_skill_command("/nope args", [_skill("greet")]) is None

    def test_expand_non_command_returns_none(self):
        bridge = SGRACPBridge()
        assert bridge._expand_skill_command("just a normal message", [_skill("greet")]) is None


class TestAcpAdvertise:
    @pytest.mark.asyncio
    async def test_new_session_advertises_skill_commands(self):
        bridge = SGRACPBridge(default_agent_name="sgr_agent")
        client = SimpleNamespace(session_update=AsyncMock())
        bridge.on_connect(client)
        cfg = _fake_cfg({"sgr_agent": "gpt-4o-mini"})
        with (
            _patch_cfg(cfg),
            patch(
                "sgr_agent_core.acp.bridge.AgentFactory._resolve_skills",
                return_value=[_skill("greet", "Greets people.")],
            ),
        ):
            await bridge.new_session(cwd="/tmp", mcp_servers=None)

        client.session_update.assert_awaited()
        update = client.session_update.await_args.args[1]
        assert isinstance(update, AvailableCommandsUpdate)
        assert [c.name for c in update.available_commands] == ["greet"]

    @pytest.mark.asyncio
    async def test_new_session_no_skills_no_advertise(self):
        bridge = SGRACPBridge(default_agent_name="sgr_agent")
        client = SimpleNamespace(session_update=AsyncMock())
        bridge.on_connect(client)
        cfg = _fake_cfg({"sgr_agent": "gpt-4o-mini"})
        with (
            _patch_cfg(cfg),
            patch(
                "sgr_agent_core.acp.bridge.AgentFactory._resolve_skills",
                return_value=[],
            ),
        ):
            await bridge.new_session(cwd="/tmp", mcp_servers=None)

        client.session_update.assert_not_awaited()
