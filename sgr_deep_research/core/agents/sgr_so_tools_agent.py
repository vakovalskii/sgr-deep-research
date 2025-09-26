from sgr_deep_research.core.agents.sgr_tools_agent import SGRToolCallingResearchAgent
from sgr_deep_research.core.tools import ReasoningTool
from sgr_deep_research.settings import get_config

config = get_config()


class SGRSOToolCallingResearchAgent(SGRToolCallingResearchAgent):
    """Agent that uses OpenAI native function calling to select and execute
    tools based on SGR like reasoning scheme."""

    name: str = "sgr_so_tool_calling_agent"

    async def _reasoning_phase(self) -> ReasoningTool:
        async with self.openai_client.chat.completions.stream(
            model=config.openai.model,
            messages=await self._prepare_context(),
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature,
            tools=await self._prepare_tools(),
            tool_choice={"type": "function", "function": {"name": ReasoningTool.tool_name}},
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    self.streaming_generator.add_chunk(event.chunk)
            reasoning: ReasoningTool = (  # noqa
                (await stream.get_final_completion()).choices[0].message.tool_calls[0].function.parsed_arguments  #
            )
        async with self.openai_client.chat.completions.stream(
            model=config.openai.model,
            response_format=ReasoningTool,
            messages=await self._prepare_context(),
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature,
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    self.streaming_generator.add_chunk(event.chunk)
        reasoning: ReasoningTool = (await stream.get_final_completion()).choices[0].message.parsed
        tool_call_result = reasoning(self._context)
        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "id": f"{self._context.iteration}-reasoning",
                        "function": {
                            "name": reasoning.tool_name,
                            "arguments": "{}",
                        },
                    }
                ],
            }
        )
        self.conversation.append(
            {"role": "tool", "content": tool_call_result, "tool_call_id": f"{self._context.iteration}-reasoning"}
        )
        self._log_reasoning(reasoning)
        return reasoning
