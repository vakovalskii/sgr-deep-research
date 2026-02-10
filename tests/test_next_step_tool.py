"""Tests for NextStepToolsBuilder."""

import pytest
from pydantic import ValidationError

from sgr_agent_core.next_step_tool import NextStepToolsBuilder
from sgr_agent_core.tools import ReasoningTool, WebSearchTool


class TestNextStepToolsBuilder:
    """Tests for NextStepToolsBuilder."""

    def test_build_ToolNameSelector_single_tool(self):
        """Test building ToolNameSelector with single tool."""
        tools_list = [ReasoningTool]
        selector_model = NextStepToolsBuilder.build_NextStepToolSelector(tools_list)

        # Create instance with valid tool name and all required ReasoningTool fields
        instance = selector_model(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["next"],
            task_completed=False,
            function_name_choice="reasoningtool",
        )
        assert instance.function_name_choice == "reasoningtool"

        # Try invalid tool name - should raise ValidationError
        with pytest.raises(ValidationError):
            selector_model(
                reasoning_steps=["step1", "step2"],
                current_situation="test",
                plan_status="ok",
                enough_data=False,
                remaining_steps=["next"],
                task_completed=False,
                tool_name="invalid_tool",
            )

    def test_build_ToolNameSelector_multiple_tools(self):
        """Test building ToolNameSelector with multiple tools."""
        tools_list = [ReasoningTool, WebSearchTool]
        selector_model = NextStepToolsBuilder.build_NextStepToolSelector(tools_list)

        # Create instance with valid tool names and all required ReasoningTool fields
        instance1 = selector_model(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["next"],
            task_completed=False,
            function_name_choice="reasoningtool",
        )
        assert instance1.function_name_choice == "reasoningtool"

        instance2 = selector_model(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["next"],
            task_completed=False,
            function_name_choice="websearchtool",
        )
        assert instance2.function_name_choice == "websearchtool"

        # Try invalid tool name - should raise ValidationError
        with pytest.raises(ValidationError):
            selector_model(
                reasoning_steps=["step1", "step2"],
                current_situation="test",
                plan_status="ok",
                enough_data=False,
                remaining_steps=["next"],
                task_completed=False,
                tool_name="invalid_tool",
            )

    def test_build_ToolNameSelector_includes_descriptions(self):
        """Test that ToolNameSelector has proper field description."""
        tools_list = [ReasoningTool, WebSearchTool]
        selector_model = NextStepToolsBuilder.build_NextStepToolSelector(tools_list)

        # Check that field description exists and is meaningful
        field_info = selector_model.model_fields["function_name_choice"]
        description = field_info.description

        assert description is not None
        assert len(description) > 0
