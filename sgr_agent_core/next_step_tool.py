from __future__ import annotations

import logging
import operator
from abc import ABC
from functools import reduce
from typing import Annotated, Literal, Type, TypeVar

from pydantic import BaseModel, Field, create_model

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.tools.reasoning_tool import ReasoningTool

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseTool)


class NextStepToolStub(ReasoningTool, ABC):
    """SGR Core - Determines the next reasoning step with adaptive planning, choosing appropriate tool
    (!) Stub class for correct autocomplete. Use NextStepToolsBuilder"""

    function: T = Field(description="Select the appropriate tool for the next step")


class ToolNameSelectorStub(ReasoningTool, ABC):
    """Stub class for tool name selection that inherits from ReasoningTool.

    Used by IronAgent to select tool name as part of reasoning phase.
    (!) Stub class for correct autocomplete. Use
    NextStepToolsBuilder.build_NextStepToolSelector
    """

    function_name_choice: str = Field(description="Select the name of the tool to use")


class DiscriminantToolMixin(BaseModel):
    tool_name_discriminator: str = Field(..., description="Tool name discriminator")

    def model_dump(self, *args, **kwargs):
        # it could cause unexpected field issues if not excluded
        exclude = kwargs.pop("exclude", set())
        exclude = exclude.union({"tool_name_discriminator"})
        return super().model_dump(*args, exclude=exclude, **kwargs)


class NextStepToolsBuilder:
    """SGR Core - Builder for NextStepTool with a dynamic union tool function type on
    pydantic models level."""

    @classmethod
    def _create_discriminant_tool(cls, tool_class: Type[T]) -> Type[BaseModel]:
        """Create a discriminant version of tool with tool_name as an instance
        field."""

        return create_model(  # noqa
            f"D_{tool_class.__name__}",
            __base__=(tool_class, DiscriminantToolMixin),  # the order matters here
            tool_name_discriminator=(Literal[tool_class.tool_name], Field(..., description="Tool name discriminator")),
        )

    @classmethod
    def _create_tool_types_union(cls, tools_list: list[Type[T]]) -> Type:
        """Create discriminated union of tools."""
        if len(tools_list) == 1:
            return cls._create_discriminant_tool(tools_list[0])
        # SGR inference struggles with choosing the right schema otherwise
        discriminant_tools = [cls._create_discriminant_tool(tool) for tool in tools_list]
        union = reduce(operator.or_, discriminant_tools)
        return Annotated[union, Field()]

    @classmethod
    def build_NextStepTools(cls, tools_list: list[Type[T]]) -> Type[NextStepToolStub]:  # noqa
        """Build a model with all NextStepTool args."""
        return create_model(
            "NextStepTools",
            __base__=NextStepToolStub,
            function=(
                cls._create_tool_types_union(tools_list),
                Field(description="Select and fill parameters of the appropriate tool for the next step"),
            ),
        )

    @classmethod
    def build_NextStepToolSelector(cls, tools_list: list[Type[T]]) -> Type[ToolNameSelectorStub]:
        """Build a model for selecting tool name."""
        # Extract tool names and descriptions
        tool_names = [tool.tool_name for tool in tools_list]

        if len(tool_names) == 1:
            literal_type = Literal[tool_names[0]]
        else:
            # Create union of individual Literal types using operator.or_
            # Literal["a"] | Literal["b"] is equivalent to Literal["a", "b"]
            literal_types = [Literal[name] for name in tool_names]
            literal_type = reduce(operator.or_, literal_types)

        # Create model dynamically, inheriting from ToolNameSelectorStub (which inherits from ReasoningTool)
        model_class = create_model(
            "NextStepToolSelector",
            __base__=ToolNameSelectorStub,
            function_name_choice=(literal_type, Field(description="Choose the name for the best tool to use")),
        )
        model_class.tool_name = "nextsteptoolselector"  # type: ignore
        return model_class
