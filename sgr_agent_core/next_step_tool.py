from __future__ import annotations

import logging
import operator
from abc import ABC
from functools import reduce
from typing import Annotated, Literal, Type, TypeVar

from pydantic import BaseModel, Field, create_model

from sgr_agent_core.base_tool import BaseTool, SystemBaseTool
from sgr_agent_core.tools.reasoning_tool import ReasoningTool

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseTool)


class NextStepToolStub(SystemBaseTool, ABC):
    """SGR Core - Determines the next reasoning step with adaptive planning, choosing appropriate tool.

    (!) Stub class for correct autocomplete. Use NextStepToolsBuilder.
    The actual base reasoning class is injected at build time.
    """

    function: T = Field(description="Select the appropriate tool for the next step")


class ToolNameSelectorStub(SystemBaseTool, ABC):
    """Stub class for tool name selection.

    Used by IronAgent to select tool name as part of reasoning phase.
    (!) Stub class for correct autocomplete. Use
    NextStepToolsBuilder.build_NextStepToolSelector with
    base_reasoning_cls. The actual base reasoning class is injected at
    build time.
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
    def build_NextStepTools(  # noqa
        cls,
        tools_list: list[Type[T]],
        base_reasoning_cls: type[ReasoningTool] = ReasoningTool,
    ) -> Type[NextStepToolStub]:
        """Build a model with all NextStepTool args.

        Args:
            tools_list: List of tool classes to include in the union.
            base_reasoning_cls: Pydantic model class used as the base for the
                reasoning schema sent to the LLM via Structured Output. Defaults
                to ReasoningTool. Pass a subclass to extend or override the
                reasoning schema.
        """
        return create_model(
            "NextStepTools",
            __base__=base_reasoning_cls,
            function=(
                cls._create_tool_types_union(tools_list),
                Field(description="Select and fill parameters of the appropriate tool for the next step"),
            ),
        )

    @classmethod
    def build_NextStepToolSelector(  # noqa
        cls,
        tools_list: list[Type[T]],
        base_reasoning_cls: type[SystemBaseTool] = ReasoningTool,
    ) -> Type[ToolNameSelectorStub]:
        """Build a model for selecting tool name.

        Args:
            tools_list: List of tool classes whose names form the allowed choices.
            base_reasoning_cls: Pydantic model class used as the base for the
                reasoning schema. Defaults to ReasoningTool. Pass a subclass to
                extend or override the reasoning schema.
        """
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
            __base__=base_reasoning_cls,
            function_name_choice=(literal_type, Field(description="Choose the name for the best tool to use")),
        )
        model_class.tool_name = "nextsteptoolselector"  # type: ignore
        return model_class
