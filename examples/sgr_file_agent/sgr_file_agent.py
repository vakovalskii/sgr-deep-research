from typing import Type

from openai import AsyncOpenAI, pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_agent_core.agent_definition import AgentConfig
from sgr_agent_core.agents.tool_calling_agent import ToolCallingAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import (
    BaseTool,
    ClarificationTool,
    FinalAnswerTool,
    ReasoningTool,
)

from .tools import (
    FindFilesFastTool,
    GetSystemPathsTool,
    ListDirectoryTool,
    ReadFileTool,
    SearchInFilesTool,
)


class SGRFileAgent(ToolCallingAgent):
    """File-first agent using native function calling only (no separate
    reasoning round-trip). Suited for OpenAI-compatible endpoints that handle
    tool_choice reliably but not structured reasoning schemas.

    Focus: File search and analysis (read-only operations)

    Available file system tools (5 essential tools):
    - GetSystemPathsTool: Get standard system paths (home, documents, downloads, desktop, etc.)
    - ListDirectoryTool: List directory contents with recursive option
      (can list current directory when path is not specified)
    - ReadFileTool: Read file contents with optional line range
    - SearchInFilesTool: Search text/code within files (grep-like functionality)
    - FindFilesFastTool: Universal file search using native find command (supports patterns, size, date filters)

    All tools use native OS commands for optimal performance.
    Automatic filtering excludes cache dirs, node_modules, .git, etc.

    Usage:
        # Via config file (recommended):
        # Set working_directory in config.yaml under agent definition:
        #   agents:
        #     sgr_file_agent:
        #       working_directory: "/path/to/work"

        # Or programmatically:
        agent = SGRFileAgent(
            max_iterations=10,
            task_messages=[{"role": "user", "content": "Find all PDF files in my Downloads folder from last week"}],
            openai_client=client,
            agent_config=config,
            toolkit=[],
            working_directory="/path/to/work"  # Optional, defaults to "."
        )
    """

    name: str = "sgr_file_agent"

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        working_directory: str | None = None,
        **kwargs: dict,
    ):
        file_system_tools = [
            GetSystemPathsTool,
            ListDirectoryTool,
            ReadFileTool,
            SearchInFilesTool,
            FindFilesFastTool,
        ]
        # Merge file system tools with provided toolkit
        merged_toolkit = file_system_tools + [t for t in toolkit if t not in file_system_tools]

        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=merged_toolkit,
            def_name=def_name,
            **kwargs,
        )
        # Get working_directory from agent_config if not provided directly
        # This allows it to be set via config file
        if working_directory is None:
            working_directory = getattr(agent_config, "working_directory", ".")
        self.working_directory = working_directory

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Build function-calling tool list for each step (filter by iteration
        limits)."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.config.execution.max_iterations:
            tools = {
                ReasoningTool,
                FinalAnswerTool,
            }
        if self._context.clarifications_used >= self.config.execution.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        return [pydantic_function_tool(tool, name=tool.tool_name) for tool in tools]

    async def _select_action_phase(self, reasoning=None) -> BaseTool:
        """Same as ToolCallingAgent, with a FinalAnswer fallback when the model
        returns no tool call (common on some gateways)."""
        phase_id = f"{self._context.iteration}-action"
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
        try:
            tool = completion.choices[0].message.tool_calls[0].function.parsed_arguments
        except (IndexError, AttributeError, TypeError):
            final_content = completion.choices[0].message.content or "Task completed successfully"
            tool = FinalAnswerTool(
                reasoning="Agent decided to complete the task",
                completed_steps=["Response synthesized without a tool call"],
                answer=final_content,
                status=AgentStatesEnum.COMPLETED,
            )
        if not isinstance(tool, BaseTool):
            raise ValueError("Selected tool is not a valid BaseTool instance")
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
