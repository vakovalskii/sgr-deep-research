import logging
import uuid
from typing import Type

from sgr_deep_research.core.agents.base_agent import BaseAgent
from sgr_deep_research.core.models import AgentStatesEnum
from sgr_deep_research.core.tools import (
    AgentCompletionTool,
    BaseTool,
    # ClarificationTool,  # Disabled - agent should not ask clarifications
    CreateReportTool,
    ExtractContentTool,
    NextStepToolsBuilder,
    NextStepToolStub,
    ReasoningTool,
    WebSearchTool,
    research_agent_tools,
    system_agent_tools,
)
from sgr_deep_research.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

config = get_config()
logger = logging.getLogger(__name__)


class SGRResearchAgent(BaseAgent):
    """Agent for deep research tasks using SGR framework."""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        # max_clarifications: int = 3,  # Disabled - agent should not ask clarifications
        max_iterations: int | None = None,
        max_searches: int = 3,  # Aligned with config.search.max_results
    ):
        super().__init__(
            task=task,
            toolkit=toolkit,
            # max_clarifications=max_clarifications,  # Disabled - agent should not ask clarifications
            max_iterations=max_iterations,
        )

        self.id = f"sgr_agent_{uuid.uuid4()}"

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
        
        # After report creation, only allow completion
        if self._context.report_created:
            tools = {
                AgentCompletionTool,
            }
            return NextStepToolsBuilder.build_NextStepTools(list(tools))
        
        # Force completion when reaching max iterations
        if self._context.iteration >= self.max_iterations:
            tools = {
                CreateReportTool,
                AgentCompletionTool,
            }
        
        # Prevent report creation without search data
        if self._context.searches_used == 0 and CreateReportTool in tools:
            tools -= {CreateReportTool}
            
        # Remove search tool when limit reached
        if self._context.searches_used >= self.max_searches:
            tools -= {WebSearchTool}
            
        return NextStepToolsBuilder.build_NextStepTools(list(tools))

    async def _reasoning_phase(self) -> NextStepToolStub:
        # Prepare request data for logging
        request_data = {
            "model": config.openai.model,
            "response_format": (await self._prepare_tools()).model_json_schema(),
            "messages": await self._prepare_context(),
            "max_tokens": config.openai.max_tokens,
            "temperature": config.openai.temperature,
        }
        
        # Log the OpenAI request
        self._log_openai_request(request_data)
        
        try:
            async with self.openai_client.chat.completions.stream(
                model=config.openai.model,
                response_format=await self._prepare_tools(),
                messages=await self._prepare_context(),
                max_tokens=config.openai.max_tokens,
                temperature=config.openai.temperature,
            ) as stream:
                async for event in stream:
                    if event.type == "chunk":
                        content = event.chunk.choices[0].delta.content
                        self.streaming_generator.add_chunk(content)
            reasoning: NextStepToolStub = (await stream.get_final_completion()).choices[0].message.parsed  # type: ignore
        except Exception as e:
            logger.error(f"❌ Reasoning phase failed: {str(e)}")
            self._context.state = AgentStatesEnum.FAILED
            raise
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
        self.streaming_generator.add_chunk(f"{result}\n")
        self._log_tool_execution(tool, result)
        return result
