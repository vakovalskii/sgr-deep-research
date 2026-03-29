from typing import Literal, Type

from openai import AsyncOpenAI
from pydantic import ValidationError

from sgr_agent_core.agent_config import AgentConfig
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import (
    BaseTool,
    FinalAnswerTool,
)


class ToolCallingAgent(BaseAgent):
    """Tool Calling Research Agent relying entirely on LLM native function
    calling."""

    name: str = "tool_calling_agent"

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
        self.tool_choice: Literal["required"] = "required"

    async def _reasoning_phase(self) -> None:
        """No explicit reasoning phase, reasoning is done internally by LLM."""
        return None

    async def _select_action_phase(self, reasoning=None) -> BaseTool:
        phase_id = f"{self._context.iteration}-action"
        _fallback_content: str = "Task completed successfully"
        completion = None
        # ValidationError can be thrown inside the stream loop when OpenAI SDK
        # tries to parse tool call arguments against the Pydantic schema.
        # Other exceptions (e.g. TypeError from invalid kwargs) must propagate.
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
                return self._append_tool_call(phase_id, tool)
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
        return self._append_tool_call(phase_id, tool)

    def _append_tool_call(self, phase_id: str, tool: BaseTool) -> BaseTool:
        """Append the selected tool call to conversation history and notify
        streaming."""
        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
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
