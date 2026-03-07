"""E2E tests for configuration pipeline.

Tests the full configuration stack from YAML/Python to AgentFactory.create()
without mocking GlobalConfig — exercises real configuration resolution.

Coverage:
- Global tool definition formats G-1 to G-4 (null, kwargs-only, kwargs, explicit ImportString)
- Agent tool reference formats A-1 to A-4 (string, string+global kwargs, dict override, dict+base_class)
- All 7 inline Python tool definition formats
- Two-level agent config building (global LLM/execution defaults + agent-specific overrides)
- Full pipeline: YAML → GlobalConfig → AgentFactory.create() → agent instance with correct
  toolkit and tool_configs
"""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import patch

import pytest
import yaml
from pydantic import Field

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_definition import AgentDefinition, ToolDefinition
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import SGRToolCallingAgent, ToolCallingAgent
from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.tools import FinalAnswerTool, ReasoningTool, WebSearchTool
from sgr_agent_core.tools.extract_page_content_tool import ExtractPageContentTool

# ── Custom tool for inline format tests ──────────────────────────────────────


class E2ETestTool(BaseTool):
    """Simple test tool for e2e config tests.

    Used in Format-5 tests (dict with null value) to verify registry
    lookup.
    """

    tool_name: ClassVar[str] = "e2e_test_tool"
    description: ClassVar[str] = "E2E test tool"

    query: str = Field(description="Query input")

    async def __call__(self, context: Any, config: Any, **kwargs: Any) -> str:
        return f"Result: {self.query}"


# ── Shared config constants ───────────────────────────────────────────────────

GLOBAL_LLM = {
    "api_key": "sk-global-key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.5,
}

# Prompts with file paths nulled out so tests don't require prompt files
MINIMAL_PROMPTS = {
    "system_prompt_str": "You are a test assistant.",
    "initial_user_request_str": "User: {user_request}",
    "clarification_response_str": "Clarification: {clarification}",
    "system_prompt_file": None,
    "initial_user_request_file": None,
    "clarification_response_file": None,
}

# Minimal LLM dict for inline AgentDefinition tests (no YAML involved)
INLINE_LLM = {"api_key": "sk-inline-key", "base_url": "https://api.openai.com/v1"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset GlobalConfig singleton before and after each test."""
    GlobalConfig._instance = None
    GlobalConfig._initialized = False
    yield
    GlobalConfig._instance = None
    GlobalConfig._initialized = False


def write_yaml_config(tmp_path, config_dict: dict) -> str:
    """Write config dict to a temp YAML file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_dict, allow_unicode=True), encoding="utf-8")
    return str(config_file)


def make_full_yaml_config() -> dict:
    """Build a full YAML config dict covering all global tool formats and agent
    variants."""
    return {
        "llm": GLOBAL_LLM,
        "execution": {"max_iterations": 5},
        "prompts": MINIMAL_PROMPTS,
        "tools": {
            # G-1: null value → base_class not set, no kwargs; resolved per-agent via ToolRegistry
            "reasoning_tool": None,
            # G-2: kwargs only, base_class inferred from ToolRegistry by name
            "web_search_tool": {
                "tavily_api_key": "tvly-global-key",
                "max_results": 10,
                "max_searches": 4,
            },
            # G-3: another kwargs-only definition
            "extract_page_content_tool": {
                "tavily_api_key": "tvly-global-key",
                "content_limit": 2000,
            },
            # G-4: explicit base_class as ImportString, no additional kwargs
            "final_answer_tool": {
                "base_class": "sgr_agent_core.tools.FinalAnswerTool",
            },
        },
        "agents": {
            # Agent with A-1 (string, empty global), A-2 (string+global kwargs),
            # A-3 (dict partial override), A-4 (dict with explicit base_class)
            "agent_standard": {
                "base_class": "sgr_agent_core.agents.SGRToolCallingAgent",
                "llm": {"model": "gpt-4o"},
                "tools": [
                    "reasoning_tool",  # A-1
                    "web_search_tool",  # A-2
                    {"extract_page_content_tool": {"content_limit": 500}},  # A-3
                    {"final_answer_tool": {"base_class": "sgr_agent_core.tools.FinalAnswerTool"}},  # A-4
                ],
            },
            # Agent that inherits all global LLM and execution settings
            "agent_inherits_global": {
                "base_class": "sgr_agent_core.agents.ToolCallingAgent",
                "tools": ["reasoning_tool", "final_answer_tool"],
            },
            # Agent that overrides model and temperature, inherits api_key and base_url
            "agent_custom_llm": {
                "base_class": "sgr_agent_core.agents.ToolCallingAgent",
                "llm": {"model": "gpt-3.5-turbo", "temperature": 0.1},
                "tools": ["final_answer_tool"],
            },
        },
    }


# ── Tests: Global tool definition formats (G-1…G-4) ──────────────────────────


class TestGlobalToolFormatsViaYAML:
    """Tests for global tool definition formats in the YAML 'tools:'
    section."""

    def test_g1_null_config_stored_without_base_class(self, tmp_path):
        """G-1: null value → ToolDefinition has no base_class and empty kwargs.

        The base_class is resolved later per-agent in agent_level_tools_validator.
        """
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))

        td = GlobalConfig().tools["reasoning_tool"]

        assert td.name == "reasoning_tool"
        assert td.base_class is None
        assert td.tool_kwargs() == {}

    def test_g2_kwargs_only_stored_with_no_base_class(self, tmp_path):
        """G-2: kwargs-only definition → ToolDefinition has kwargs but no base_class."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))

        td = GlobalConfig().tools["web_search_tool"]

        assert td.name == "web_search_tool"
        assert td.base_class is None
        assert td.tool_kwargs() == {
            "tavily_api_key": "tvly-global-key",
            "max_results": 10,
            "max_searches": 4,
        }

    def test_g3_multiple_kwargs_stored_correctly(self, tmp_path):
        """G-3: kwargs-only for extract_page_content_tool → all kwargs preserved."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))

        td = GlobalConfig().tools["extract_page_content_tool"]

        assert td.tool_kwargs() == {
            "tavily_api_key": "tvly-global-key",
            "content_limit": 2000,
        }

    def test_g4_explicit_base_class_import_string_resolved(self, tmp_path):
        """G-4: explicit base_class ImportString → resolved to actual Python class."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))

        td = GlobalConfig().tools["final_answer_tool"]

        assert td.base_class is FinalAnswerTool
        assert td.tool_kwargs() == {}  # base_class excluded from kwargs


# ── Tests: Agent tool reference formats (A-1…A-4) ────────────────────────────


class TestAgentToolFormatsViaYAML:
    """Tests for agent-level tool reference formats after YAML loading.

    All assertions target the resolved AgentDefinition.tools list, where
    agent_level_tools_validator has already merged global kwargs and
    resolved base_class to an actual Python class.
    """

    def _load_agent_standard(self, tmp_path) -> AgentDefinition:
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        return GlobalConfig().agents["agent_standard"]

    def test_a1_string_tool_empty_global_resolved_from_registry(self, tmp_path):
        """A-1: string tool with null global → base_class from ToolRegistry, empty kwargs."""
        agent = self._load_agent_standard(tmp_path)
        td = agent.tools[0]  # "reasoning_tool"

        assert td.name == "reasoning_tool"
        assert td.base_class is ReasoningTool
        assert td.tool_kwargs() == {}

    def test_a2_string_tool_inherits_all_global_kwargs(self, tmp_path):
        """A-2: string tool reference inherits full kwargs from global definition."""
        agent = self._load_agent_standard(tmp_path)
        td = agent.tools[1]  # "web_search_tool"

        assert td.name == "web_search_tool"
        assert td.base_class is WebSearchTool
        assert td.tool_kwargs() == {
            "tavily_api_key": "tvly-global-key",
            "max_results": 10,
            "max_searches": 4,
        }

    def test_a3_dict_tool_partial_override_merges_with_global(self, tmp_path):
        """A-3: dict tool overrides content_limit; tavily_api_key inherited from global."""
        agent = self._load_agent_standard(tmp_path)
        td = agent.tools[2]  # {"extract_page_content_tool": {"content_limit": 500}}

        assert td.name == "extract_page_content_tool"
        assert td.base_class is ExtractPageContentTool
        kwargs = td.tool_kwargs()
        assert kwargs["content_limit"] == 500  # agent-level override
        assert kwargs["tavily_api_key"] == "tvly-global-key"  # inherited from global

    def test_a4_dict_tool_with_explicit_base_class_import_string(self, tmp_path):
        """A-4: dict tool specifying base_class ImportString → resolved to class."""
        agent = self._load_agent_standard(tmp_path)
        td = agent.tools[3]  # {"final_answer_tool": {"base_class": "..."}}

        assert td.name == "final_answer_tool"
        assert td.base_class is FinalAnswerTool
        assert td.tool_kwargs() == {}

    def test_tool_list_length_and_order_matches_yaml(self, tmp_path):
        """Agent tools list has exact count and order as defined in YAML."""
        agent = self._load_agent_standard(tmp_path)

        assert len(agent.tools) == 4
        assert [td.name for td in agent.tools] == [
            "reasoning_tool",
            "web_search_tool",
            "extract_page_content_tool",
            "final_answer_tool",
        ]

    def test_all_agent_tools_have_resolved_base_class(self, tmp_path):
        """After loading, every ToolDefinition in agent.tools has a concrete
        class."""
        agent = self._load_agent_standard(tmp_path)

        for td in agent.tools:
            assert isinstance(td.base_class, type), f"Tool '{td.name}' has unresolved base_class: {td.base_class!r}"
            assert issubclass(td.base_class, BaseTool)


# ── Tests: All 7 inline Python tool definition formats ───────────────────────


class TestInlineToolDefinitionFormats:
    """Tests for all 7 inline Python formats supported by
    AgentDefinition.tools.

    These tests create AgentDefinition objects directly in Python
    without loading any YAML, so GlobalConfig.tools is empty and global
    kwargs merging does not apply.
    """

    _COMMON = dict(
        name="test_agent",
        base_class=ToolCallingAgent,
        llm=INLINE_LLM,
        prompts=MINIMAL_PROMPTS,
        execution={},
    )

    def _make_agent(self, tools: list) -> AgentDefinition:
        return AgentDefinition(**self._COMMON, tools=tools)

    def test_format_1_string_name_resolved_from_registry(self):
        """Format 1: plain string → base_class from ToolRegistry, no kwargs."""
        agent = self._make_agent(["reasoning_tool", "final_answer_tool"])
        td = agent.tools[0]

        assert td.name == "reasoning_tool"
        assert td.base_class is ReasoningTool
        assert td.tool_kwargs() == {}

    def test_format_2_class_passed_directly(self):
        """Format 2: class object → tool_name taken from class attribute."""
        agent = self._make_agent([WebSearchTool, FinalAnswerTool])
        td = agent.tools[0]

        assert td.name == WebSearchTool.tool_name
        assert td.base_class is WebSearchTool

    def test_format_3_tool_definition_with_class(self):
        """Format 3: ToolDefinition(base_class=SomeClass) → class preserved as-is."""
        agent = self._make_agent(
            [
                ToolDefinition(name="final_answer_tool", base_class=FinalAnswerTool),
                ReasoningTool,
            ]
        )
        td = agent.tools[0]

        assert td.name == "final_answer_tool"
        assert td.base_class is FinalAnswerTool
        assert td.tool_kwargs() == {}

    def test_format_4_tool_definition_with_import_string(self):
        """Format 4: ToolDefinition(base_class=ImportString) → Pydantic resolves to class."""
        agent = self._make_agent(
            [
                ToolDefinition(
                    name="reasoning_as_import",
                    base_class="sgr_agent_core.tools.ReasoningTool",
                ),
                FinalAnswerTool,
            ]
        )
        td = agent.tools[0]

        assert td.name == "reasoning_as_import"
        assert td.base_class is ReasoningTool

    def test_format_5_dict_null_value_equivalent_to_string(self):
        """Format 5: {tool_name: None} → same result as bare string format."""
        agent = self._make_agent([{"e2e_test_tool": None}, FinalAnswerTool])
        td = agent.tools[0]

        assert td.name == "e2e_test_tool"
        assert td.base_class is E2ETestTool
        assert td.tool_kwargs() == {}

    def test_format_6_dict_with_inline_kwargs(self):
        """Format 6: {tool_name: {kwargs}} → tool receives the specified kwargs."""
        agent = self._make_agent(
            [
                {"web_search_tool": {"max_results": 2, "tavily_api_key": "tvly-inline"}},
                FinalAnswerTool,
            ]
        )
        td = agent.tools[0]

        assert td.name == "web_search_tool"
        assert td.base_class is WebSearchTool
        assert td.tool_kwargs() == {"max_results": 2, "tavily_api_key": "tvly-inline"}

    def test_format_7_dict_with_base_class_import_string(self):
        """Format 7: {tool_name: {base_class: ImportString}} → ImportString resolved to class."""
        agent = self._make_agent(
            [
                {"reasoning_as_import": {"base_class": "sgr_agent_core.tools.ReasoningTool"}},
                FinalAnswerTool,
            ]
        )
        td = agent.tools[0]

        assert td.name == "reasoning_as_import"
        assert td.base_class is ReasoningTool

    def test_all_7_formats_coexist_in_one_agent_definition(self):
        """All 7 inline formats can be combined in a single AgentDefinition."""
        agent = self._make_agent(
            [
                "reasoning_tool",  # Format 1
                WebSearchTool,  # Format 2
                ToolDefinition(name="final_answer_tool", base_class=FinalAnswerTool),  # Format 3
                ToolDefinition(  # Format 4
                    name="reasoning_via_import",
                    base_class="sgr_agent_core.tools.ReasoningTool",
                ),
                {"e2e_test_tool": None},  # Format 5
                {
                    "extract_page_content_tool": {
                        "content_limit": 800,  # Format 6
                        "tavily_api_key": "tvly-k",
                    }
                },
                {"reasoning_named": {"base_class": "sgr_agent_core.tools.ReasoningTool"}},  # Format 7
            ]
        )

        assert len(agent.tools) == 7

        names = {td.name for td in agent.tools}
        assert "reasoning_tool" in names
        assert "final_answer_tool" in names
        assert "reasoning_via_import" in names
        assert "e2e_test_tool" in names
        assert "extract_page_content_tool" in names
        assert "reasoning_named" in names

        for td in agent.tools:
            assert isinstance(td.base_class, type)
            assert issubclass(td.base_class, BaseTool)


# ── Tests: Two-level agent config building ────────────────────────────────────


class TestAgentConfigTwoLevelBuilding:
    """Tests for two-level agent config: global defaults + agent-specific overrides.

    Level 1: GlobalConfig provides llm, execution, prompts defaults.
    Level 2: AgentDefinition overrides specific fields; unspecified fields inherited.

    This mirrors how tool definitions work (global defaults + agent-level overrides)
    but applied to the full agent configuration.
    """

    def test_agent_overrides_model_inherits_global_api_key_and_base_url(self, tmp_path):
        """Level-2 model override leaves api_key, base_url, temperature from
        Level-1."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent = GlobalConfig().agents["agent_standard"]

        assert agent.llm.model == "gpt-4o"  # agent-level override
        assert agent.llm.api_key == "sk-global-key"  # inherited from global
        assert agent.llm.base_url == "https://api.openai.com/v1"  # inherited from global
        assert agent.llm.temperature == 0.5  # inherited from global

    def test_agent_without_llm_section_inherits_full_global_llm(self, tmp_path):
        """Agent with no 'llm:' section gets the complete global LLM
        configuration."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent = GlobalConfig().agents["agent_inherits_global"]

        assert agent.llm.model == "gpt-4o-mini"  # from global
        assert agent.llm.api_key == "sk-global-key"  # from global
        assert agent.llm.temperature == 0.5  # from global
        assert agent.llm.base_url == "https://api.openai.com/v1"  # from global

    def test_agent_overrides_multiple_llm_fields(self, tmp_path):
        """Agent overrides both model and temperature; api_key and base_url
        inherited."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent = GlobalConfig().agents["agent_custom_llm"]

        assert agent.llm.model == "gpt-3.5-turbo"  # agent-level override
        assert agent.llm.temperature == 0.1  # agent-level override
        assert agent.llm.api_key == "sk-global-key"  # inherited from global
        assert agent.llm.base_url == "https://api.openai.com/v1"  # inherited from global

    def test_agent_inherits_global_execution_max_iterations(self, tmp_path):
        """Agent without 'execution:' section inherits global
        max_iterations."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent = GlobalConfig().agents["agent_inherits_global"]

        assert agent.execution.max_iterations == 5  # from global

    def test_agent_overrides_one_execution_field_inherits_rest(self, tmp_path):
        """Agent overrides max_iterations; default max_clarifications still
        applies."""
        config = make_full_yaml_config()
        config["agents"]["agent_exec_override"] = {
            "base_class": "sgr_agent_core.agents.ToolCallingAgent",
            "execution": {"max_iterations": 20},
            "tools": ["final_answer_tool"],
        }
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, config))
        agent = GlobalConfig().agents["agent_exec_override"]

        assert agent.execution.max_iterations == 20  # agent override
        assert agent.execution.max_clarifications == 3  # ExecutionConfig default unchanged

    def test_multiple_agents_have_independent_resolved_llm_configs(self, tmp_path):
        """Multiple agents in same YAML each get their own correctly resolved
        LLM."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))

        agent_a = GlobalConfig().agents["agent_standard"]
        agent_b = GlobalConfig().agents["agent_inherits_global"]
        agent_c = GlobalConfig().agents["agent_custom_llm"]

        assert agent_a.llm.model == "gpt-4o"
        assert agent_b.llm.model == "gpt-4o-mini"
        assert agent_c.llm.model == "gpt-3.5-turbo"

        for agent in (agent_a, agent_b, agent_c):
            assert agent.llm.api_key == "sk-global-key"


# ── Tests: Full E2E pipeline ──────────────────────────────────────────────────


class TestFullPipelineE2E:
    """Tests for the complete pipeline: YAML → GlobalConfig → AgentFactory.create().

    These tests verify that AgentFactory correctly builds toolkit and tool_configs
    from the fully resolved AgentDefinition produced by GlobalConfig.from_yaml().
    MCP is mocked to avoid external connections.
    """

    @pytest.mark.asyncio
    async def test_yaml_agent_toolkit_contains_correct_classes(self, tmp_path):
        """Full pipeline: agent.toolkit has exactly the classes defined in YAML."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent_def = GlobalConfig().agents["agent_standard"]

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent = await AgentFactory.create(
                agent_def,
                task_messages=[{"role": "user", "content": "Test task"}],
            )

        assert ReasoningTool in agent.toolkit
        assert WebSearchTool in agent.toolkit
        assert ExtractPageContentTool in agent.toolkit
        assert FinalAnswerTool in agent.toolkit
        assert len(agent.toolkit) == 4

    @pytest.mark.asyncio
    async def test_yaml_agent_tool_configs_reflect_merged_kwargs(self, tmp_path):
        """Full pipeline: tool_configs contain correctly merged global + agent kwargs."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent_def = GlobalConfig().agents["agent_standard"]

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent = await AgentFactory.create(
                agent_def,
                task_messages=[{"role": "user", "content": "Test task"}],
            )

        # A-1: reasoning_tool — no global kwargs, so empty
        assert agent.tool_configs.get(ReasoningTool.tool_name) == {}

        # A-2: web_search_tool — fully inherited from global
        assert agent.tool_configs.get(WebSearchTool.tool_name) == {
            "tavily_api_key": "tvly-global-key",
            "max_results": 10,
            "max_searches": 4,
        }

        # A-3: content_limit overridden, tavily_api_key inherited
        extract_cfg = agent.tool_configs.get(ExtractPageContentTool.tool_name)
        assert extract_cfg["content_limit"] == 500
        assert extract_cfg["tavily_api_key"] == "tvly-global-key"

        # A-4: final_answer_tool — no kwargs
        assert agent.tool_configs.get(FinalAnswerTool.tool_name) == {}

    @pytest.mark.asyncio
    async def test_yaml_agent_id_prefixed_with_definition_name(self, tmp_path):
        """Agent created via factory has id starting with definition name from
        YAML."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent_def = GlobalConfig().agents["agent_standard"]

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent = await AgentFactory.create(
                agent_def,
                task_messages=[{"role": "user", "content": "Test task"}],
            )

        assert agent.id.startswith("agent_standard_")

    @pytest.mark.asyncio
    async def test_yaml_agent_uses_correct_base_class(self, tmp_path):
        """Agent created via factory is an instance of the base_class in
        YAML."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        agent_def = GlobalConfig().agents["agent_standard"]

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent = await AgentFactory.create(
                agent_def,
                task_messages=[{"role": "user", "content": "Test task"}],
            )

        assert isinstance(agent, SGRToolCallingAgent)

    @pytest.mark.asyncio
    async def test_agent_overrides_global_kwargs_in_tool_configs(self, tmp_path):
        """Agent-level kwargs take priority over global kwargs in the final
        tool_configs."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        # agent_standard overrides extract_page_content_tool.content_limit: 500 (global was 2000)
        agent_def = GlobalConfig().agents["agent_standard"]

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent = await AgentFactory.create(
                agent_def,
                task_messages=[{"role": "user", "content": "Priority test"}],
            )

        cfg = agent.tool_configs[ExtractPageContentTool.tool_name]
        assert cfg["content_limit"] == 500  # agent override wins
        assert cfg["tavily_api_key"] == "tvly-global-key"  # global-only field preserved

    @pytest.mark.asyncio
    async def test_inline_agent_definition_full_pipeline(self):
        """Inline Python AgentDefinition → AgentFactory.create() → correct
        agent."""
        agent_def = AgentDefinition(
            name="inline_agent",
            base_class=ToolCallingAgent,
            llm=INLINE_LLM,
            prompts=MINIMAL_PROMPTS,
            tools=[
                "reasoning_tool",
                {"web_search_tool": {"max_results": 5, "tavily_api_key": "tvly-inline"}},
                FinalAnswerTool,
            ],
        )

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent = await AgentFactory.create(
                agent_def,
                task_messages=[{"role": "user", "content": "Inline test"}],
            )

        assert isinstance(agent, ToolCallingAgent)
        assert ReasoningTool in agent.toolkit
        assert WebSearchTool in agent.toolkit
        assert FinalAnswerTool in agent.toolkit
        assert agent.tool_configs[WebSearchTool.tool_name] == {
            "max_results": 5,
            "tavily_api_key": "tvly-inline",
        }

    @pytest.mark.asyncio
    async def test_two_agents_from_same_yaml_have_independent_tool_configs(self, tmp_path):
        """Agents loaded from same YAML have independent tool_configs dicts."""
        GlobalConfig.from_yaml(write_yaml_config(tmp_path, make_full_yaml_config()))
        def_standard = GlobalConfig().agents["agent_standard"]
        def_inherits = GlobalConfig().agents["agent_inherits_global"]

        with patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]):
            agent_a = await AgentFactory.create(
                def_standard,
                task_messages=[{"role": "user", "content": "Task A"}],
            )
            agent_b = await AgentFactory.create(
                def_inherits,
                task_messages=[{"role": "user", "content": "Task B"}],
            )

        assert agent_a.id != agent_b.id
        assert len(agent_a.toolkit) == 4
        assert len(agent_b.toolkit) == 2
