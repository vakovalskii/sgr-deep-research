from typing import Type

from openai import AsyncOpenAI

from sgr_agent_core.agent_definition import AgentConfig
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.next_step_tool import NextStepToolsBuilder
from sgr_agent_core.tools import (
    BaseTool,
    NextStepToolStub,
)


class SGRAgent(BaseAgent):
    """Agent for deep research tasks using an SGR framework."""

    name: str = "sgr_agent"

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

    async def _prepare_tools(self) -> Type[NextStepToolStub]:
        """Prepare available tools for the current agent state and progress."""
        tools = set(self.toolkit)
        return NextStepToolsBuilder.build_NextStepTools(list(tools))

    async def _reasoning_phase(self) -> NextStepToolStub:
        phase_id = f"{self._context.iteration}-reasoning"
        async with self.openai_client.chat.completions.stream(
            response_format=await self._prepare_tools(),
            messages=await self._prepare_context(),
            **self.config.llm.to_openai_client_kwargs(),
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    self.streaming_generator.add_chunk(event.chunk, phase_id)
        reasoning: NextStepToolStub = (await stream.get_final_completion()).choices[0].message.parsed  # type: ignore
        # we are not fully sure if it should be in conversation or not. Looks like not necessary data
        # self.conversation.append({"role": "assistant", "content": reasoning.model_dump_json(exclude={"function"})})

        self.streaming_generator.add_tool_call(phase_id, reasoning)
        self._log_reasoning(reasoning)
        return reasoning

    async def _select_action_phase(self, reasoning: NextStepToolStub) -> BaseTool:
        phase_id = f"{self._context.iteration}-action"
        tool = reasoning.function
        if not isinstance(tool, BaseTool):
            raise ValueError("Selected tool is not a valid BaseTool instance")
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
