"""Tests for the use_skill invocation tool (Layer 3/4)."""

import pytest

from sgr_agent_core.models import AgentContext
from sgr_agent_core.skills import BaseSkill, SkillMetadata
from sgr_agent_core.tools.skill_tool import SkillTool


def _skill(name, description="A skill.", body="BODY"):
    return BaseSkill(metadata=SkillMetadata(name=name, description=description), body=body)


class TestSkillTool:
    def test_tool_registration_metadata(self):
        assert SkillTool.tool_name == "use_skill"
        assert SkillTool.isSystemTool is True
        assert SkillTool.description

    @pytest.mark.asyncio
    async def test_returns_skill_body_when_found(self):
        ctx = AgentContext(available_skills=[_skill("greet", body="Say hello nicely.")])
        tool = SkillTool(skill_name="greet")
        result = await tool(ctx, None)
        assert "Say hello nicely." in result
        assert "greet" in result

    @pytest.mark.asyncio
    async def test_returns_error_with_available_when_not_found(self):
        ctx = AgentContext(available_skills=[_skill("alpha"), _skill("beta")])
        tool = SkillTool(skill_name="missing")
        result = await tool(ctx, None)
        assert "missing" in result
        assert "alpha" in result and "beta" in result

    @pytest.mark.asyncio
    async def test_no_skills_available(self):
        ctx = AgentContext()
        tool = SkillTool(skill_name="whatever")
        result = await tool(ctx, None)
        assert "whatever" in result


class TestAgentContextSkills:
    def test_available_skills_default_empty(self):
        assert AgentContext().available_skills == []

    def test_available_skills_excluded_from_state(self):
        ctx = AgentContext(available_skills=[_skill("greet")])
        # available_skills must not bloat the serialized agent state.
        assert "available_skills" not in ctx.agent_state()
