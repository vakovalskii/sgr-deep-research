"""Tests for exposing skills as MCP prompts (Layer 5, MCP surface)."""

import pytest

from sgr_agent_core.skills import Skill, SkillMetadata
from sgr_agent_core.skills.mcp_server import build_skills_mcp_server


def _skill(name, description="A skill.", body="BODY", **kw):
    return Skill(metadata=SkillMetadata(name=name, description=description, **kw), body=body)


class TestSkillsMcpServer:
    @pytest.mark.asyncio
    async def test_skills_registered_as_prompts(self):
        server = build_skills_mcp_server([_skill("greet", "Greets people.", "Greet warmly.")])
        prompts = await server.list_prompts()
        by_name = {p.name: p for p in prompts}
        assert "greet" in by_name
        assert by_name["greet"].description == "Greets people."

    @pytest.mark.asyncio
    async def test_prompt_renders_skill_body(self):
        server = build_skills_mcp_server([_skill("greet", body="Greet warmly.")])
        rendered = await server.render_prompt("greet", {})
        assert "Greet warmly." in rendered.messages[0].content.text

    @pytest.mark.asyncio
    async def test_prompt_appends_arguments(self):
        server = build_skills_mcp_server([_skill("greet", body="Greet warmly.")])
        rendered = await server.render_prompt("greet", {"arguments": "to Bob"})
        text = rendered.messages[0].content.text
        assert "Greet warmly." in text and "to Bob" in text

    @pytest.mark.asyncio
    async def test_non_user_invocable_excluded(self):
        server = build_skills_mcp_server([_skill("shown", "Shown."), _skill("hidden", "Hidden.", user_invocable=False)])
        prompts = await server.list_prompts()
        names = {p.name for p in prompts}
        assert "shown" in names and "hidden" not in names
