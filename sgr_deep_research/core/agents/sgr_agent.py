from typing import Type

from sgr_deep_research.core.agents.base_agent import BaseAgent
from sgr_deep_research.core.tools import (
    AgentCompletionTool,
    BaseTool,
    ClarificationTool,
    CreateReportTool,
    NextStepToolsBuilder,
    NextStepToolStub,
    ReasoningTool,
    SimpleAnswerTool,
    WebSearchTool,
    research_agent_tools,
    system_agent_tools,
)
from sgr_deep_research.settings import get_config

config = get_config()


class SGRResearchAgent(BaseAgent):
    """Agent for deep research tasks using SGR framework."""

    name: str = "sgr_agent"

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        max_clarifications: int = 3,
        max_iterations: int = 10,
        max_searches: int = 4,
    ):
        super().__init__(
            task=task,
            toolkit=toolkit,
            max_clarifications=max_clarifications,
            max_iterations=max_iterations,
        )

        self.toolkit = [
            *system_agent_tools,
            *research_agent_tools,
            *(toolkit or []),
        ]
        self.toolkit.remove(ReasoningTool)  # we use our own reasoning scheme
        self.max_searches = max_searches

    async def _prepare_tools(self) -> Type[NextStepToolStub]:
        """Prepare tool classes with current context limits."""
        tools = set(self.toolkit)
        
        # If report has been created, only allow completion
        if getattr(self._context, 'report_created', False):
            tools = {
                AgentCompletionTool,
            }
        elif self._context.iteration >= self.max_iterations:
            tools = {
                CreateReportTool,
                SimpleAnswerTool,
                AgentCompletionTool,
            }
        
        if self._context.clarifications_used >= self.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        if self._context.searches_used >= self.max_searches:
            tools -= {
                WebSearchTool,
            }
        return NextStepToolsBuilder.build_NextStepTools(list(tools))

    async def _reasoning_phase(self) -> NextStepToolStub:
        async with self.openai_client.chat.completions.stream(
            model=config.openai.model,
            response_format=await self._prepare_tools(),
            messages=await self._prepare_context(),
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature,
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    self.streaming_generator.add_chunk(event.chunk)
        reasoning: NextStepToolStub = (await stream.get_final_completion()).choices[0].message.parsed  # type: ignore
        # we are not fully sure if it should be in conversation or not. Looks like not necessary data
        # self.conversation.append({"role": "assistant", "content": reasoning.model_dump_json(exclude={"function"})})
        self._log_reasoning(reasoning)
        return reasoning

    async def _select_action_phase(self, reasoning: NextStepToolStub) -> BaseTool:
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
                        "id": f"{self._context.iteration}-action",
                        "function": {
                            "name": tool.tool_name,
                            "arguments": tool.model_dump_json(),
                        },
                    }
                ],
            }
        )
        self.streaming_generator.add_tool_call(
            f"{self._context.iteration}-action", tool.tool_name, tool.model_dump_json()
        )
        return tool

    async def _action_phase(self, tool: BaseTool) -> str:
        result = tool(self._context)
        self.conversation.append(
            {"role": "tool", "content": result, "tool_call_id": f"{self._context.iteration}-action"}
        )
        self.streaming_generator.add_chunk_from_str(f"{result}\n")
        self._log_tool_execution(tool, result)
        return result
