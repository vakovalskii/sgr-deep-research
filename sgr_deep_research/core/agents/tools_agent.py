import logging
import uuid
from typing import Literal, Type

from openai import pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_deep_research.core.agents.base_agent import BaseAgent
from sgr_deep_research.core.tools import (
    AgentCompletionTool,
    BaseTool,
    # ClarificationTool,  # Disabled - agent should not ask clarifications
    CreateReportTool,
    ExtractContentTool,
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


class ToolCallingResearchAgent(BaseAgent):
    """Tool Calling Research Agent relying entirely on LLM native function
    calling."""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        # max_clarifications: int = 3,  # Disabled - agent should not ask clarifications
        max_searches: int = 3,  # Aligned with config.search.max_results
        max_iterations: int | None = None,
    ):
        super().__init__(
            task=task,
            toolkit=toolkit,
            # max_clarifications=max_clarifications,  # Disabled - agent should not ask clarifications
            max_iterations=max_iterations,
        )
        self.id = f"tool_calling_agent_{uuid.uuid4()}"

        self.toolkit = [*system_agent_tools, *research_agent_tools, *(toolkit if toolkit else [])]
        self.toolkit.remove(ReasoningTool)  # LLM will do the reasoning internally

        self.max_searches = max_searches
        self.tool_choice: Literal["required"] = "required"

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare tool classes with current context limits."""
        tools = set(self.toolkit)
        
        # Force completion if max iterations reached
        if self._context.iteration >= self.max_iterations:
            tools = [
                CreateReportTool,
                AgentCompletionTool,
            ]
        # Prevent CreateReportTool if no searches performed - FORCE data collection first
        elif self._context.searches_used == 0:
            tools -= {
                CreateReportTool,
            }
        
        # Clarification tool is completely disabled for this agent
        # if self._context.clarifications_used >= self.max_clarifications:
        #     tools -= {
        #         ClarificationTool,
        #     }
        if self._context.searches_used >= self.max_searches:
            tools -= {
                WebSearchTool,
            }
        return [pydantic_function_tool(tool, name=tool.tool_name, description=tool.description) for tool in tools]

    async def _reasoning_phase(self) -> None:
        """No explicit reasoning phase, reasoning is done internally by LLM."""
        return None

    async def _select_action_phase(self, reasoning=None) -> BaseTool:
        # Prepare request data for logging
        request_data = {
            "model": config.openai.model,
            "messages": await self._prepare_context(),
            "max_tokens": config.openai.max_tokens,
            "temperature": config.openai.temperature,
            "tools": [tool.model_dump() for tool in await self._prepare_tools()],
            "tool_choice": self.tool_choice,
        }
        
        # Log the OpenAI request
        self._log_openai_request(request_data)
        
        async with self.openai_client.chat.completions.stream(
            model=config.openai.model,
            messages=await self._prepare_context(),
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature,
            tools=await self._prepare_tools(),
            tool_choice=self.tool_choice,
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    content = event.chunk.choices[0].delta.content
                    self.streaming_generator.add_chunk(content)
        tool = (await stream.get_final_completion()).choices[0].message.tool_calls[0].function.parsed_arguments

        if not isinstance(tool, BaseTool):
            raise ValueError("Selected tool is not a valid BaseTool instance")
        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
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
