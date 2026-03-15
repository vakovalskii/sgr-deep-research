"""Tests for agent definition classes.

This module contains tests for AgentDefinition and ToolDefinition,
including ImportString validation for tools.
"""

from unittest.mock import Mock, patch

import pytest

from sgr_agent_core.agent_definition import (
    AgentDefinition,
    ExecutionConfig,
    LLMConfig,
    PromptsConfig,
    ToolDefinition,
)
from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.tools import ReasoningTool


class TestToolDefinition:
    """Tests for ToolDefinition class."""

    def test_tool_definition_with_none_base_class(self):
        """Test ToolDefinition with base_class=None (default)."""
        tool_def = ToolDefinition(name="test_tool")
        assert tool_def.name == "test_tool"
        assert tool_def.base_class is None

    def test_tool_definition_with_class_base_class(self):
        """Test ToolDefinition with base_class as a class."""
        tool_def = ToolDefinition(name="test_tool", base_class=ReasoningTool)
        assert tool_def.name == "test_tool"
        assert tool_def.base_class == ReasoningTool
        assert issubclass(tool_def.base_class, BaseTool)

    def test_tool_definition_with_string_base_class(self):
        """Test ToolDefinition with base_class as a string (no dots)."""
        tool_def = ToolDefinition(name="test_tool", base_class="ReasoningTool")
        assert tool_def.name == "test_tool"
        assert tool_def.base_class == "ReasoningTool"

    def test_tool_definition_with_import_string_base_class(self):
        """Test ToolDefinition with base_class as ImportString (dotted
        path)."""
        # Pydantic automatically imports the class from ImportString
        tool_def = ToolDefinition(name="test_tool", base_class="sgr_agent_core.tools.ReasoningTool")
        assert tool_def.name == "test_tool"
        # base_class should be imported as a class, not a string
        assert tool_def.base_class == ReasoningTool
        assert issubclass(tool_def.base_class, BaseTool)

    def test_tool_definition_with_import_string_validates_module_exists(self):
        """Test ToolDefinition validates that ImportString module exists."""
        # Valid import string should pass and import the class
        tool_def = ToolDefinition(name="test_tool", base_class="sgr_agent_core.tools.ReasoningTool")
        assert tool_def.base_class == ReasoningTool
        assert issubclass(tool_def.base_class, BaseTool)

    def test_tool_definition_with_invalid_import_string_raises_error(self):
        """Test ToolDefinition raises FileNotFoundError for invalid
        ImportString."""
        # ModuleNotFoundError is raised by importlib, which is caught and converted to FileNotFoundError
        with pytest.raises(FileNotFoundError, match="base_class import.*could not be found"):
            ToolDefinition(name="test_tool", base_class="nonexistent.module.NonExistentTool")

    def test_tool_definition_validates_base_class_is_tool_when_class(self):
        """Test ToolDefinition validates base_class is BaseTool subclass when
        it's a class."""
        # Valid tool class should pass
        tool_def = ToolDefinition(name="test_tool", base_class=ReasoningTool)
        assert tool_def.base_class == ReasoningTool

    def test_tool_definition_rejects_non_tool_class(self):
        """Test ToolDefinition rejects class that is not a BaseTool
        subclass."""

        class NotATool:
            """A class that is not a BaseTool subclass."""

            pass

        with pytest.raises(TypeError, match="Imported base_class must be a subclass of BaseTool"):
            ToolDefinition(name="test_tool", base_class=NotATool)

    def test_tool_definition_string_representation(self):
        """Test ToolDefinition string representation."""
        tool_def = ToolDefinition(name="test_tool", base_class=ReasoningTool)
        str_repr = str(tool_def)
        assert "ToolDefinition" in str_repr
        assert "test_tool" in str_repr
        assert "ReasoningTool" in str_repr

    def test_tool_definition_string_representation_with_string_base_class(self):
        """Test ToolDefinition string representation with ImportString
        base_class."""
        # Pydantic imports the class from ImportString, so base_class becomes a class
        tool_def = ToolDefinition(name="test_tool", base_class="sgr_agent_core.tools.ReasoningTool")
        str_repr = str(tool_def)
        assert "ToolDefinition" in str_repr
        assert "test_tool" in str_repr
        # When ImportString is imported, it becomes a class, so __str__ shows class name
        assert "ReasoningTool" in str_repr

    def test_tool_definition_string_representation_with_none_base_class(self):
        """Test ToolDefinition string representation with None base_class."""
        tool_def = ToolDefinition(name="test_tool", base_class=None)
        str_repr = str(tool_def)
        assert "ToolDefinition" in str_repr
        assert "test_tool" in str_repr

    def test_tool_definition_with_single_dot_import_string(self):
        """Test ToolDefinition with ImportString that has only one dot."""
        # Single dot with 2 parts should trigger validation, but module doesn't exist
        # This should raise FileNotFoundError because module 'tools' is not found
        with pytest.raises(FileNotFoundError, match="base_class import.*could not be found"):
            ToolDefinition(name="test_tool", base_class="tools.ReasoningTool")

    def test_tool_definition_with_empty_string_base_class(self):
        """Test ToolDefinition with empty string base_class."""
        # Empty string should not trigger ImportString validation
        tool_def = ToolDefinition(name="test_tool", base_class="")
        assert tool_def.base_class == ""

    def test_tool_definition_with_import_string_no_dots(self):
        """Test ToolDefinition with string base_class that has no dots."""
        # String without dots should not trigger ImportString validation
        tool_def = ToolDefinition(name="test_tool", base_class="ReasoningTool")
        assert tool_def.base_class == "ReasoningTool"


class TestAgentDefinitionTools:
    """Tests for AgentDefinition.tools field (list of str, type, or dict with
    single-key compact format)."""

    def test_tools_dict_with_non_dict_config_value_raises_value_error(self):
        """Compact dict format {tool_name: value} requires value to be dict or
        null.

        A non-dict, non-null value (e.g. an integer) must raise a clear
        ValueError.
        """
        from pydantic import ValidationError

        mock_config = Mock()
        mock_config.llm = LLMConfig(api_key="key", base_url="https://api.openai.com/v1")
        mock_config.prompts = PromptsConfig(
            system_prompt_str="p", initial_user_request_str="p", clarification_response_str="p"
        )
        mock_config.execution = ExecutionConfig()
        mock_config.search = None
        mock_mcp = Mock()
        mock_mcp.model_copy.return_value = mock_mcp
        mock_mcp.model_dump.return_value = {}
        mock_config.mcp = mock_mcp
        with (
            patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config),
            pytest.raises(ValidationError, match="must be a dict or null"),
        ):
            AgentDefinition(
                name="test_agent",
                base_class="sgr_agent_core.agents.SGRAgent",
                tools=[{"reasoning_tool": 10}],  # invalid: config value must be dict or null
                llm={"api_key": "key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "p",
                    "initial_user_request_str": "p",
                    "clarification_response_str": "p",
                },
            )

    def test_tools_dict_with_multiple_keys_raises_value_error(self):
        """Compact dict format requires exactly one key: {tool_name: config}.

        A dict with more than one key is ambiguous and must raise a clear error.
        """
        from pydantic import ValidationError

        mock_config = Mock()
        mock_config.llm = LLMConfig(api_key="key", base_url="https://api.openai.com/v1")
        mock_config.prompts = PromptsConfig(
            system_prompt_str="p", initial_user_request_str="p", clarification_response_str="p"
        )
        mock_config.execution = ExecutionConfig()
        mock_config.search = None
        mock_mcp = Mock()
        mock_mcp.model_copy.return_value = mock_mcp
        mock_mcp.model_dump.return_value = {}
        mock_config.mcp = mock_mcp
        with (
            patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config),
            pytest.raises(ValidationError, match="not a valid tool definition"),
        ):
            AgentDefinition(
                name="test_agent",
                base_class="sgr_agent_core.agents.SGRAgent",
                tools=[{"tool_a": {}, "tool_b": {}}],  # invalid: two keys in one dict
                llm={"api_key": "key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "p",
                    "initial_user_request_str": "p",
                    "clarification_response_str": "p",
                },
            )
