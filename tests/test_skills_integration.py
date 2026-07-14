"""Integration tests: skills wired through config, BaseAgent, and AgentFactory (Layer 4)."""

from unittest.mock import Mock, patch

import pytest
from openai import AsyncOpenAI

from sgr_agent_core.agent_definition import (
    AgentConfig,
    AgentDefinition,
    ExecutionConfig,
    LangfuseConfig,
    LLMConfig,
    PromptsConfig,
)
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import SGRToolCallingAgent
from sgr_agent_core.skills import Skill, SkillMetadata, SkillsConfig
from sgr_agent_core.tools.reasoning_tool import ReasoningTool
from sgr_agent_core.tools.skill_tool import SkillTool
from tests.conftest import create_test_agent


def _skill(name, description="A skill.", body="BODY"):
    return Skill(metadata=SkillMetadata(name=name, description=description), body=body)


def _write_skill(root, name, description="A skill.", body="Do the thing."):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_default_skill_roots(monkeypatch):
    """Keep tests hermetic: only use skills.paths, never the machine's global
    ~/.sgr/skills or <config_dir>/skills locations."""
    monkeypatch.setattr(
        AgentFactory,
        "_default_skill_roots",
        classmethod(lambda cls, cfg: [__import__("pathlib").Path(p) for p in cfg.paths]),
    )


class TestAgentConfigSkills:
    def test_agent_config_accepts_skills(self):
        cfg = AgentConfig(skills={"enabled": True, "paths": ["./skills"], "max_desc_chars": 300})
        assert isinstance(cfg.skills, SkillsConfig)
        assert cfg.skills.paths == ["./skills"]
        assert cfg.skills.max_desc_chars == 300

    def test_agent_config_skills_default_none(self):
        assert AgentConfig().skills is None


class TestBaseAgentSkills:
    def test_agent_stores_and_injects_skills(self):
        agent = create_test_agent(SGRToolCallingAgent, toolkit=[ReasoningTool])
        agent.available_skills = [_skill("greet", "Greets people.", body="Say hi")]
        agent._context.available_skills = agent.available_skills
        assert agent.available_skills[0].name == "greet"

    @pytest.mark.asyncio
    async def test_prepare_context_renders_skills(self):
        agent = create_test_agent(SGRToolCallingAgent, toolkit=[ReasoningTool])
        agent.available_skills = [_skill("greet", "Greets people.")]
        # PromptsConfig test fixture uses a plain string without placeholders,
        # so swap in a template that references {available_skills}.
        agent.config.prompts.system_prompt_str = "Tools:{available_tools}\nSkills:{available_skills}"
        messages = await agent._prepare_context()
        system = messages[0]["content"]
        assert "greet: Greets people." in system
        assert "use_skill" in system


class TestAgentFactorySkills:
    @pytest.mark.asyncio
    async def test_factory_resolves_skills_and_adds_skill_tool(self, tmp_path):
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, "greet", "Greets people.", "Say hi warmly.")

        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            patch.object(AgentFactory, "_create_client", return_value=Mock(spec=AsyncOpenAI)),
        ):
            agent_def = AgentDefinition(
                name="skilled_agent",
                base_class=SGRToolCallingAgent,
                tools=["reasoningtool"],
                llm=LLMConfig(api_key="test-key", base_url="https://api.openai.com/v1"),
                prompts=PromptsConfig(
                    system_prompt_str="Test",
                    initial_user_request_str="Test",
                    clarification_response_str="Test",
                ),
                execution=ExecutionConfig(),
                langfuse=LangfuseConfig(),
                skills=SkillsConfig(paths=[str(skills_root)]),
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "hi"}])

            assert [s.name for s in agent.available_skills] == ["greet"]
            assert SkillTool in agent.toolkit

    @pytest.mark.asyncio
    async def test_factory_no_skills_no_skill_tool(self, tmp_path):
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            patch.object(AgentFactory, "_create_client", return_value=Mock(spec=AsyncOpenAI)),
        ):
            agent_def = AgentDefinition(
                name="plain_agent",
                base_class=SGRToolCallingAgent,
                tools=["reasoningtool"],
                llm=LLMConfig(api_key="test-key", base_url="https://api.openai.com/v1"),
                prompts=PromptsConfig(
                    system_prompt_str="Test",
                    initial_user_request_str="Test",
                    clarification_response_str="Test",
                ),
                execution=ExecutionConfig(),
                langfuse=LangfuseConfig(),
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "hi"}])
            assert agent.available_skills == []
            assert SkillTool not in agent.toolkit

    @pytest.mark.asyncio
    async def test_factory_include_allowlist(self, tmp_path):
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, "alpha", "Alpha.")
        _write_skill(skills_root, "beta", "Beta.")
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            patch.object(AgentFactory, "_create_client", return_value=Mock(spec=AsyncOpenAI)),
        ):
            agent_def = AgentDefinition(
                name="allow_agent",
                base_class=SGRToolCallingAgent,
                tools=["reasoningtool"],
                llm=LLMConfig(api_key="k", base_url="https://api.openai.com/v1"),
                prompts=PromptsConfig(
                    system_prompt_str="T", initial_user_request_str="T", clarification_response_str="T"
                ),
                execution=ExecutionConfig(),
                langfuse=LangfuseConfig(),
                skills=SkillsConfig(paths=[str(skills_root)], include=["beta"]),
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "hi"}])
            assert [s.name for s in agent.available_skills] == ["beta"]

    @pytest.mark.asyncio
    async def test_factory_empty_include_keeps_all(self, tmp_path):
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, "alpha", "Alpha.")
        _write_skill(skills_root, "beta", "Beta.")
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            patch.object(AgentFactory, "_create_client", return_value=Mock(spec=AsyncOpenAI)),
        ):
            agent_def = AgentDefinition(
                name="empty_include_agent",
                base_class=SGRToolCallingAgent,
                tools=["reasoningtool"],
                llm=LLMConfig(api_key="k", base_url="https://api.openai.com/v1"),
                prompts=PromptsConfig(
                    system_prompt_str="T", initial_user_request_str="T", clarification_response_str="T"
                ),
                execution=ExecutionConfig(),
                langfuse=LangfuseConfig(),
                skills=SkillsConfig(paths=[str(skills_root)], include=[]),
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "hi"}])
            assert [s.name for s in agent.available_skills] == ["alpha", "beta"]

    @pytest.mark.asyncio
    async def test_factory_exclude_filter(self, tmp_path):
        skills_root = tmp_path / "skills"
        _write_skill(skills_root, "alpha", "Alpha.")
        _write_skill(skills_root, "beta", "Beta.")

        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            patch.object(AgentFactory, "_create_client", return_value=Mock(spec=AsyncOpenAI)),
        ):
            agent_def = AgentDefinition(
                name="filtered_agent",
                base_class=SGRToolCallingAgent,
                tools=["reasoningtool"],
                llm=LLMConfig(api_key="test-key", base_url="https://api.openai.com/v1"),
                prompts=PromptsConfig(
                    system_prompt_str="Test",
                    initial_user_request_str="Test",
                    clarification_response_str="Test",
                ),
                execution=ExecutionConfig(),
                langfuse=LangfuseConfig(),
                skills=SkillsConfig(paths=[str(skills_root)], exclude=["beta"]),
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "hi"}])
            assert [s.name for s in agent.available_skills] == ["alpha"]
