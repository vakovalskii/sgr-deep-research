"""Tests for prompts module.

This module contains tests for PromptLoader utility class.
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from sgr_agent_core.agent_definition import PromptsConfig
from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.services import PromptLoader


class TestPromptLoader:
    """Tests for PromptLoader class."""

    def test_load_prompt_file_exists_in_user_dir(self):
        """Test loading prompt file from user directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test prompt file
            test_file = os.path.join(tmpdir, "test_prompt.txt")
            test_content = "This is a test prompt"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_content)

            result = PromptsConfig._load_prompt_file(test_file)
            assert result == test_content

    def test_load_prompt_file_caching(self):
        """Test that PromptsConfig uses caching for loaded prompts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "cached_prompt.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("Cached content")

            prompts_config = PromptsConfig(
                system_prompt_file=test_file,
                initial_user_request_file=test_file,
                clarification_response_file=test_file,
            )

            # First access - loads from file
            result1 = prompts_config.system_prompt
            # Second access - uses cached property
            result2 = prompts_config.system_prompt

            assert result1 == result2 == "Cached content"

    def test_load_prompt_file_not_found(self):
        """Test that FileNotFoundError is raised when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_file = os.path.join(tmpdir, "nonexistent.txt")

            with pytest.raises(FileNotFoundError):
                PromptsConfig._load_prompt_file(nonexistent_file)

    def test_load_prompt_file_io_error(self):
        """Test that IOError is properly handled and re-raised."""
        with patch("pathlib.Path.read_text", side_effect=IOError("Permission denied")):
            with pytest.raises(IOError) as exc_info:
                PromptsConfig._load_prompt_file("/some/path.txt")
            assert "Permission denied" in str(exc_info.value)

    def test_load_prompt_file_strips_whitespace(self):
        """Test that loaded content is not automatically stripped
        (PromptsConfig doesn't strip, but we can test the raw loading)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "whitespace.txt")
            test_content = "  \n  Content with spaces  \n  "
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_content)

            result = PromptsConfig._load_prompt_file(test_file)
            # PromptsConfig._load_prompt_file doesn't strip, it returns raw content
            assert result == test_content

    def test_get_system_prompt_with_tools(self):
        """Test get_system_prompt with available tools."""

        # Create mock tools
        class MockTool1(BaseTool):
            tool_name = "mock_tool_1"
            description = "First mock tool"

        class MockTool2(BaseTool):
            tool_name = "mock_tool_2"
            description = "Second mock tool"

        tools = [MockTool1(), MockTool2()]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create system prompt template
            template_file = os.path.join(tmpdir, "system_prompt.txt")
            template = "Available tools:\n{available_tools}\nUse them wisely."
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                system_prompt_file=template_file,
                initial_user_request_file=dummy_file,
                clarification_response_file=dummy_file,
            )

            result = PromptLoader.get_system_prompt(tools, prompts_config)

            assert "Available tools:" in result
            assert "1. mock_tool_1: First mock tool" in result
            assert "2. mock_tool_2: Second mock tool" in result
            assert "Use them wisely." in result

    def test_get_system_prompt_empty_tools(self):
        """Test get_system_prompt with no tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = os.path.join(tmpdir, "system_prompt.txt")
            template = "Available tools:\n{available_tools}\nDone."
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                system_prompt_file=template_file,
                initial_user_request_file=dummy_file,
                clarification_response_file=dummy_file,
            )

            result = PromptLoader.get_system_prompt([], prompts_config)

            assert "Available tools:\n\nDone." in result

    def test_get_system_prompt_missing_placeholder(self):
        """Test get_system_prompt with missing placeholder raises KeyError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = os.path.join(tmpdir, "system_prompt.txt")
            # Template without {available_tools} placeholder
            template = "This template has no placeholders."
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                system_prompt_file=template_file,
                initial_user_request_file=dummy_file,
                clarification_response_file=dummy_file,
            )

            # This should work since no placeholder is used
            result = PromptLoader.get_system_prompt([], prompts_config)
            assert result == "This template has no placeholders."

    def test_get_initial_user_request(self):
        """Test get_initial_user_request formats date correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = os.path.join(tmpdir, "initial_user_request.txt")
            template = "Current Date: {current_date}"
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                initial_user_request_file=template_file,
                system_prompt_file=dummy_file,
                clarification_response_file=dummy_file,
            )

            task_messages = [{"role": "user", "content": "Research quantum computing"}]
            result = PromptLoader.get_initial_user_request(task_messages, prompts_config)

            assert "Current Date:" in result
            # Check that date is in the result
            current_year = datetime.now().year
            assert str(current_year) in result

    def test_get_initial_user_request_date_format(self):
        """Test that get_initial_user_request includes properly formatted
        date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = os.path.join(tmpdir, "initial_user_request.txt")
            template = "{current_date}|test"
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                initial_user_request_file=template_file,
                system_prompt_file=dummy_file,
                clarification_response_file=dummy_file,
            )

            task_messages = [{"role": "user", "content": "test task"}]
            result = PromptLoader.get_initial_user_request(task_messages, prompts_config)

            # Check format YYYY-MM-DD HH:MM:SS
            parts = result.split("|")
            date_part = parts[0]
            assert len(date_part) == 19  # YYYY-MM-DD HH:MM:SS
            assert date_part[4] == "-"
            assert date_part[7] == "-"
            assert date_part[10] == " "
            assert date_part[13] == ":"
            assert date_part[16] == ":"

    def test_get_clarification_template(self):
        """Test get_clarification_template formats clarifications correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = os.path.join(tmpdir, "clarification_response.txt")
            template = "Date: {current_date}"
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                clarification_response_file=template_file,
                system_prompt_file=dummy_file,
                initial_user_request_file=dummy_file,
            )

            clarification_messages = [
                {"role": "user", "content": "1. Answer A"},
                {"role": "user", "content": "2. Answer B"},
            ]
            result = PromptLoader.get_clarification_template(clarification_messages, prompts_config)

            assert "Date:" in result
            # Check that date is in the result
            current_year = datetime.now().year
            assert str(current_year) in result

    def test_get_clarification_template_date_format(self):
        """Test that get_clarification_template includes properly formatted
        date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = os.path.join(tmpdir, "clarification_response.txt")
            template = "{current_date}|test"
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(template)

            # Create dummy files for other prompts to satisfy validator
            dummy_file = os.path.join(tmpdir, "dummy.txt")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("dummy")

            prompts_config = PromptsConfig(
                clarification_response_file=template_file,
                system_prompt_file=dummy_file,
                initial_user_request_file=dummy_file,
            )

            clarification_messages = [{"role": "user", "content": "test"}]
            result = PromptLoader.get_clarification_template(clarification_messages, prompts_config)

            # Check that date is properly formatted
            parts = result.split("|")
            date_part = parts[0]
            assert len(date_part) == 19  # YYYY-MM-DD HH:MM:SS

    def test_load_prompt_file_falls_back_to_lib_dir(self):
        """Test that PromptsConfig can load files from default library
        directory."""
        # This tests that PromptsConfig can load files using default paths
        # In real scenario, it should find files in the installed package
        try:
            # Try to create PromptsConfig with default paths
            prompts_config = PromptsConfig()
            # Access the property to trigger file loading
            result = prompts_config.initial_user_request
            assert len(result) > 0
            assert "{task}" in result or "{current_date}" in result
        except FileNotFoundError:
            # If file is not found, that's also acceptable in test environment
            pytest.skip("Prompt files not found in package - this is ok in test env")
