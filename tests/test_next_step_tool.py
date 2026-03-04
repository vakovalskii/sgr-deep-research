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

        field_info = selector_model.model_fields["function_name_choice"]
        description = field_info.description

        assert description is not None
        assert len(description) > 0

    def test_stubs_do_not_inherit_reasoning_tool(self):
        """NextStepToolStub and ToolNameSelectorStub are SystemBaseTool-based,
        not ReasoningTool."""
        from sgr_agent_core.base_tool import SystemBaseTool
        from sgr_agent_core.next_step_tool import NextStepToolStub, ToolNameSelectorStub

        assert not issubclass(NextStepToolStub, ReasoningTool)
        assert not issubclass(ToolNameSelectorStub, ReasoningTool)
        assert issubclass(NextStepToolStub, SystemBaseTool)
        assert issubclass(ToolNameSelectorStub, SystemBaseTool)

    def test_build_NextStepToolSelector_default_base_has_reasoning_fields(self):
        """build_NextStepToolSelector default base injects ReasoningTool
        fields."""
        selector_model = NextStepToolsBuilder.build_NextStepToolSelector([WebSearchTool])
        assert issubclass(selector_model, ReasoningTool)

    def test_build_NextStepToolSelector_custom_base_reasoning_cls(self):
        """build_NextStepToolSelector uses custom base_reasoning_cls."""
        from pydantic import Field as PydanticField

        class CustomReasoningTool(ReasoningTool):
            custom_field: str = PydanticField(default="custom")

        selector_model = NextStepToolsBuilder.build_NextStepToolSelector(
            [WebSearchTool],
            base_reasoning_cls=CustomReasoningTool,
        )
        assert issubclass(selector_model, CustomReasoningTool)
        assert "custom_field" in selector_model.model_fields
