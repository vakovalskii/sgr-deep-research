from openai import pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from examples.sgr_deep_research.agents import ResearchSGRToolCallingAgent
from sgr_agent_core.tools import ExtractPageContentTool, FinalAnswerTool, ReasoningTool, WebSearchTool


class BenchmarkAgent(ResearchSGRToolCallingAgent):
    """Agent for benchmarking with automatic tool selection."""

    name: str = "benchmark_agent"

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.toolkit = [
            ReasoningTool,
            WebSearchTool,
            ExtractPageContentTool,
            FinalAnswerTool,
        ]

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for current agent state and progress."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.max_iterations:
            tools = {
                ReasoningTool,
                FinalAnswerTool,
            }
        if self._context.searches_used >= self.max_searches:
            tools -= {
                WebSearchTool,
            }

        return [pydantic_function_tool(tool, name=tool.tool_name, description="") for tool in tools]

    async def execute(
        self,
    ):
        await super().execute()
