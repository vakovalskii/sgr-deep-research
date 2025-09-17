import logging
import uuid
from typing import Literal, Type

from openai import pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_deep_research.core.agents.sgr_agent import SGRResearchAgent
from sgr_deep_research.core.models import AgentStatesEnum
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


class SGRToolCallingResearchAgent(SGRResearchAgent):
    """Agent that uses OpenAI native function calling to select and execute
    tools based on SGR like reasoning scheme."""

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
            max_searches=max_searches,
        )
        self.id = f"sgr_tool_calling_agent_{uuid.uuid4()}"
        self.toolkit = [*system_agent_tools, *research_agent_tools, *(toolkit if toolkit else [])]
        self.tool_choice: Literal["required"] = "required"

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for current agent state and progress."""
        tools = set(self.toolkit)
        
        # After report creation, only allow completion
        if self._context.report_created:
            tools = [
                ReasoningTool,
                AgentCompletionTool,
            ]
            return [pydantic_function_tool(tool, name=tool.tool_name, description=tool.description) for tool in tools]
        
        # Force completion if max iterations reached
        if self._context.iteration >= self.max_iterations:
            tools = [
                ReasoningTool,
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

    async def _reasoning_phase(self) -> ReasoningTool:
        # Prepare request data for logging
        request_data = {
            "model": config.openai.model,
            "messages": await self._prepare_context(),
            "max_tokens": config.openai.max_tokens,
            "temperature": config.openai.temperature,
            "tools": [tool.model_dump() for tool in await self._prepare_tools()],
            "tool_choice": {"type": "function", "function": {"name": ReasoningTool.tool_name}},
        }
        
        # Log the OpenAI request
        self._log_openai_request(request_data)
        
        try:
            async with self.openai_client.chat.completions.stream(
                model=config.openai.model,
                messages=await self._prepare_context(),
                max_tokens=config.openai.max_tokens,
                temperature=config.openai.temperature,
                tools=await self._prepare_tools(),
                tool_choice={"type": "function", "function": {"name": ReasoningTool.tool_name}},
            ) as stream:
                async for event in stream:
                    # print(event)
                    if event.type == "chunk":
                        content = event.chunk.choices[0].delta.content
                        self.streaming_generator.add_chunk(content)
                reasoning: ReasoningTool = (  # noqa
                    (await stream.get_final_completion()).choices[0].message.tool_calls[0].function.parsed_arguments  #
                )
        except Exception as e:
            logger.error(f"❌ Reasoning phase failed: {str(e)}")
            self._context.state = AgentStatesEnum.FAILED
            raise
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
                            "arguments": reasoning.model_dump_json(),
                        },
                    }
                ],
            }
        )
        tool_call_result = reasoning(self._context)
        self.conversation.append(
            {"role": "tool", "content": tool_call_result, "tool_call_id": f"{self._context.iteration}-reasoning"}
        )
        self._log_reasoning(reasoning)
        return reasoning

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
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
        
        try:
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
        except Exception as e:
            logger.error(f"❌ Action selection failed: {str(e)}")
            self._context.state = AgentStatesEnum.FAILED
            raise

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
