"""Fuzzy Agent that doesn't rely on tool calling or structured output."""

from datetime import datetime
from typing import Type

from openai import AsyncOpenAI
from pydantic import BaseModel

from sgr_agent_core.agent_config import AgentConfig
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.next_step_tool import NextStepToolsBuilder
from sgr_agent_core.services.registry import ToolRegistry
from sgr_agent_core.services.tool_instantiator import ToolInstantiator
from sgr_agent_core.tools import BaseTool, ReasoningTool, ToolNameSelectorStub


class IronAgent(BaseAgent):
    """Agent that uses flexible parsing of LLM text responses instead of tool
    calling.

    This agent doesn't rely on:
    - Tool calling (function calling)
    - Structured output (response_format)

    Instead, it parses natural language responses from LLM to determine
    which tool to use and with what parameters using ToolInstantiator.
    """

    name: str = "iron_agent"

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=toolkit,
            def_name=def_name,
            **kwargs,
        )

    def _log_tool_instantiator(
        self,
        instantiator: ToolInstantiator,
        attempt: int,
        max_retries: int,
    ):
        """Log tool generation attempt by LLM using data from ToolInstantiator.

        Args:
            instantiator: ToolInstantiator instance with attempt data
            attempt: Current attempt number (1-based)
            max_retries: Maximum number of retry attempts
        """
        success = instantiator.instance is not None
        errors_formatted = instantiator.input_content + "\n" + "\n".join(instantiator.errors)
        self.logger.info(
            f"""
###############################################
TOOL GENERATION DEBUG
    {"✅" if success else "❌"}  ATTEMPT {attempt}/{max_retries} {"SUCCESS" if success else "FAILED"}:

    Tool: {instantiator.tool_class.tool_name} - Class: {instantiator.tool_class.__name__}

{errors_formatted if not success else ""}
###############################################"""
        )

        self.log.append(
            {
                "step_number": self._context.iteration,
                "timestamp": datetime.now().isoformat(),
                "step_type": "tool_generation_attempt",
                "tool_class": instantiator.tool_class.__name__,
                "attempt": attempt,
                "max_retries": max_retries,
                "success": success,
                "llm_content": instantiator.input_content,
                "errors": instantiator.errors.copy(),
            }
        )

    async def _generate_tool(
        self,
        tool_class: Type[BaseTool],
        messages: list[dict],
        max_retries: int = 5,
    ) -> BaseTool | BaseModel:
        """Generate tool instance from LLM response using ToolInstantiator.

        Universal method for calling LLM with parsing through ToolInstantiator.
        Handles retries with error accumulation.

        Args:
            tool_class: Tool class or model class to instantiate
            messages: Context messages for LLM
            max_retries: Maximum number of retry attempts

        Returns:
            Instance of tool_class

        Raises:
            ValueError: If parsing fails after max_retries attempts
        """
        instantiator = ToolInstantiator(tool_class)

        for attempt in range(max_retries):
            async with self.openai_client.chat.completions.stream(
                messages=messages + [{"role": "user", "content": instantiator.generate_format_prompt()}],
                **self.config.llm.to_openai_client_kwargs(),
            ) as stream:
                phase_id = f"{self._context.iteration}-generate"
                async for event in stream:
                    if event.type == "chunk":
                        self.streaming_generator.add_chunk(event.chunk, phase_id)

                completion = await stream.get_final_completion()
                content = completion.choices[0].message.content
                try:
                    tool_instance = instantiator.build_model(content)
                    return tool_instance
                except ValueError:
                    continue
                finally:
                    self._log_tool_instantiator(
                        instantiator=instantiator,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                    )

        raise ValueError(
            f"Failed to parse {tool_class.__name__} after {max_retries} attempts. "
            f"Try to simplify tool schema or provide more detailed instructions."
        )

    async def _prepare_tools(self) -> Type[ToolNameSelectorStub]:
        """Prepare available tools for the current agent state and progress."""
        if self._context.iteration >= self.config.execution.max_iterations:
            raise RuntimeError("Max iterations reached")
        return NextStepToolsBuilder.build_NextStepToolSelector(self.toolkit)

    async def _reasoning_phase(self) -> ReasoningTool:
        """Call LLM to get ReasoningTool with selected tool name."""
        messages = await self._prepare_context()

        tool_selector_model = await self._prepare_tools()
        reasoning = await self._generate_tool(tool_selector_model, messages)

        if not isinstance(reasoning, ReasoningTool):
            raise ValueError("Expected ReasoningTool instance")

        # Log reasoning
        self._log_reasoning(reasoning)

        # Add to streaming
        self.streaming_generator.add_tool_call(f"{self._context.iteration}-reasoning", reasoning)

        return reasoning

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
        """Select tool based on reasoning phase result."""
        messages = await self._prepare_context()

        tool_name = reasoning.function_name_choice  # type: ignore

        # Find tool class by name
        tool_class: Type[BaseTool] | None = None

        # Try ToolRegistry first
        tool_class = ToolRegistry.get(tool_name)

        # If not found, search in toolkit
        if tool_class is None:
            for tool in self.toolkit:
                if tool.tool_name == tool_name:
                    tool_class = tool
                    break

        if tool_class is None:
            raise ValueError(f"Tool '{tool_name}' not found in toolkit")

        # Generate tool parameters
        tool = await self._generate_tool(tool_class, messages)

        if not isinstance(tool, BaseTool):
            raise ValueError("Selected tool is not a valid BaseTool instance")

        # Add to conversation
        self.conversation.append(
            {
                "role": "assistant",
                "content": reasoning.remaining_steps[0] if reasoning.remaining_steps else "Completing",
                "tool_calls": [
                    {
                        "type": "function",
                        "id": f"{self._context.iteration}-action",
                        "function": {
                            "name": tool.tool_name,
                            "arguments": tool.model_dump_json(),
                        },
                    }
                ],
            }
        )
        self.streaming_generator.add_tool_call(f"{self._context.iteration}-action", tool)

        return tool

    async def _action_phase(self, tool: BaseTool) -> str:
        """Execute selected tool."""
        phase_id = f"{self._context.iteration}-action"
        result = await tool(self._context, self.config, **self.tool_configs.get(tool.tool_name, {}))
        self.conversation.append({"role": "tool", "content": result, "tool_call_id": phase_id})
        self.streaming_generator.add_tool_result(phase_id, result, tool.tool_name)
        self._log_tool_execution(tool, result)
        return result
