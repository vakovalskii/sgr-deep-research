from typing import Literal, Type

from openai import AsyncOpenAI, pydantic_function_tool
from pydantic import ValidationError

from sgr_agent_core.agent_config import AgentConfig
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import (
    BaseTool,
    FinalAnswerTool,
    ReasoningTool,
    SystemBaseTool,
)


class SGRToolCallingAgent(BaseAgent):
    """Agent that uses OpenAI native function calling to select and execute
    tools based on SGR like a reasoning scheme."""

    name: str = "sgr_tool_calling_agent"

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        *,
        def_name: str | None = None,
        reasoning_tool_cls: type[SystemBaseTool] = ReasoningTool,
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
        self.tool_choice: Literal["required"] = "required"
        self.ReasoningTool: type[SystemBaseTool] = reasoning_tool_cls

    async def _reasoning_phase(self) -> ReasoningTool:
        phase_id = f"{self._context.iteration}-reasoning"
        async with self.openai_client.chat.completions.stream(
            messages=await self._prepare_context(),
            tools=[pydantic_function_tool(self.ReasoningTool, name=self.ReasoningTool.tool_name)],
            tool_choice=self.tool_choice,
            **self.config.llm.to_openai_client_kwargs(),
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    self.streaming_generator.add_chunk(event.chunk, phase_id)
            final_completion = await stream.get_final_completion()
        reasoning: ReasoningTool = final_completion.choices[0].message.tool_calls[0].function.parsed_arguments
        self.streaming_generator.add_tool_call(phase_id, reasoning)
        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "id": phase_id,
                        "function": {
                            "name": reasoning.tool_name,
                            "arguments": reasoning.model_dump_json(),
                        },
                    }
                ],
            }
        )
        tool_call_result = await reasoning(self._context, self.config)
        self.streaming_generator.add_tool_result(phase_id, tool_call_result, reasoning.tool_name)
        self.conversation.append({"role": "tool", "content": tool_call_result, "tool_call_id": phase_id})
        self._log_reasoning(reasoning)
        return reasoning

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
        phase_id = f"{self._context.iteration}-action"
        _fallback_content: str = "Task completed successfully"
        completion = None
        try:
            async with self.openai_client.chat.completions.stream(
                messages=await self._prepare_context(),
                tools=await self._prepare_tools(),
                tool_choice=self.tool_choice,
                **self.config.llm.to_openai_client_kwargs(),
            ) as stream:
                async for event in stream:
                    if event.type == "chunk":
                        self.streaming_generator.add_chunk(event.chunk, phase_id)
                completion = await stream.get_final_completion()
        except ValidationError as exc:
            self.logger.warning("Streaming validation error (%s), falling back to FinalAnswerTool", exc)
        if completion is not None:
            try:
                _fallback_content = completion.choices[0].message.content or _fallback_content
                tool = completion.choices[0].message.tool_calls[0].function.parsed_arguments
                if not isinstance(tool, BaseTool):
                    raise TypeError(f"parsed_arguments returned {type(tool).__name__}, expected BaseTool")
                self.conversation.append(
                    {
                        "role": "assistant",
                        "content": reasoning.remaining_steps[0] if reasoning.remaining_steps else "Completing",
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": phase_id,
                                "function": {
                                    "name": tool.tool_name,
                                    "arguments": tool.model_dump_json(),
                                },
                            }
                        ],
                    }
                )
                self.streaming_generator.add_tool_call(phase_id, tool)
                return tool
            except (IndexError, AttributeError, TypeError, ValidationError) as exc:
                self.logger.warning(
                    "Tool call parsing failed (%s: %s), falling back to FinalAnswerTool", type(exc).__name__, exc
                )
        tool = FinalAnswerTool(
            reasoning="Agent decided to complete the task",
            completed_steps=["Response synthesized without a tool call"],
            answer=_fallback_content,
            status=AgentStatesEnum.COMPLETED,
        )
        self.conversation.append(
            {
                "role": "assistant",
                "content": reasoning.remaining_steps[0] if reasoning.remaining_steps else "Completing",
                "tool_calls": [
                    {
                        "type": "function",
                        "id": phase_id,
                        "function": {
                            "name": tool.tool_name,
                            "arguments": tool.model_dump_json(),
                        },
                    }
                ],
            }
        )
        self.streaming_generator.add_tool_call(phase_id, tool)
        return tool

    async def _action_phase(self, tool: BaseTool) -> str:
        phase_id = f"{self._context.iteration}-action"
        result = await tool(self._context, self.config, **self.tool_configs.get(tool.tool_name, {}))
        self.conversation.append({"role": "tool", "content": result, "tool_call_id": phase_id})
        self.streaming_generator.add_tool_result(phase_id, result, tool.tool_name)
        self._log_tool_execution(tool, result)
        return result
