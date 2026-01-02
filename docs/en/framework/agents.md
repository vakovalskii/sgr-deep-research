# Build Your Agent

This section dives into the technical implementation of agents and explores how to adapt them to your needs.

!!! Tip "Agent Architecture"
    Information about available agents and their differences can be found in [Main Concepts](main-concepts.md#agent).


*For a detailed understanding of the full logic, it's better to familiarize yourself with the [source code](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_agent.py).*

## Interface

Simplified representation of the main execution cycle:
```py
while agent.state not in FINISH_STATES:
    reasoning = await agent._reasoning_phase()
    action_tool = await agent._select_action_phase(reasoning)
    await agent._action_phase(action_tool)
```


`BaseAgent` provides a minimal interface for modifying agent behavior and working with context.

### Core Agent Attributes

```py
class BaseAgent:
    # Identification
    id: str                                    # Unique agent identifier
    name: str                                  # Agent class name
    task: str                                  # Task to execute

    # Configuration and clients
    config: AgentConfig                        # Agent configuration
    openai_client: AsyncOpenAI                 # Client for LLM API interaction

    # Context and state
    _context: AgentContext                    # Agent execution context
    conversation: list[dict]                  # Conversation history with LLM

    # Tools and streaming
    toolkit: list[Type[BaseTool]]             # Set of available tools
    streaming_generator: OpenAIStreamingGenerator  # Streaming generator
```

### Methods to Override

When creating custom solutions, pay attention first and foremost to these methods:
```py

    async def _prepare_context(self) -> list[dict]:
        """Prepare a conversation context with system prompt, task data and any
        other context. Override this method to change the context setup for the
        agent.

        Returns a list of dictionaries OpenAI like format, each containing a role and
        content key by default.
        """
        return [
            {"role": "system", "content": PromptLoader.get_system_prompt(self.toolkit, self.config.prompts)},
            {
                "role": "user",
                "content": PromptLoader.get_initial_user_request(self.task, self.config.prompts),
            },
            *self.conversation,
        ]

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for the current agent state and progress.
        Override this method to change the tool setup or conditions for tool
        usage.

        Returns a list of ChatCompletionFunctionToolParam based
        available tools.
        """
        tools = set(self.toolkit)
        if self._context.iteration >= self.config.execution.max_iterations:
            raise RuntimeError("Max iterations reached")
        return [pydantic_function_tool(tool, name=tool.tool_name) for tool in tools]

    async def _reasoning_phase(self) -> ReasoningTool:
        """Call LLM to decide next action based on current context."""
        raise NotImplementedError("_reasoning_phase must be implemented by subclass")

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
        """Select the most suitable tool for the action decided in the
        reasoning phase.

        Returns the tool suitable for the action.
        """
        raise NotImplementedError("_select_action_phase must be implemented by subclass")

    async def _action_phase(self, tool: BaseTool) -> str:
        """Call Tool for the action decided in the select_action phase.

        Returns string or dumped JSON result of the tool execution.
        """
        raise NotImplementedError("_action_phase must be implemented by subclass")

    async def _execution_step(self):
        """Execute a single step of the agent workflow.

        Note: Override this method to change the agent workflow for each step.
        """
        raise NotImplementedError("_execution_step must be implemented by subclass")
```
## Core Agent Modules


### AgentConfig

Stores all agent settings: LLM parameters, search, execution, prompts, and MCP configuration.

!!! Tip "More about configuration"
    Full description of the configuration system, settings hierarchy, and usage examples can be found in the [configuration guide](configuration.md).

#### Extending Configuration

Existing config schemas allow extending fields without modifying the base class:

**Example 1: Adding fields in YAML**

```yaml
agents:
  custom_agent:
    base_class: "SGRAgent"
    execution:
      max_iterations: 15
      # Custom fields
      custom_timeout: 300
      retry_count: 5
      enable_caching: true
    tools:
      - "WebSearchTool"
      - "FinalAnswerTool"
```

**Example 2: Using custom fields in AgentDefinition**

```python
from sgr_agent_core import AgentDefinition
from sgr_agent_core.agent_definition import ExecutionConfig
from sgr_agent_core.agents import SGRAgent

# Custom fields can be added directly to ExecutionConfig
agent_def = AgentDefinition(
    name="custom_agent",
    base_class=SGRAgent,
    execution=ExecutionConfig(
        max_iterations=15,
        custom_timeout=600,
        retry_count=5,
        enable_caching=True
),
    tools=["WebSearchTool", "FinalAnswerTool"]
)
```

**Example 3: Using custom fields in agent**

```python
class CustomAgent(BaseAgent):
    async def _action_phase(self, tool: BaseTool) -> str:
        # Direct access to custom fields
        timeout = self.config.execution.custom_timeout
        retry_count = self.config.execution.retry_count

        if self.config.execution.enable_caching:
            # Caching logic
            pass

        result = await tool(self._context, self.config)
        return result
```

!!! Important "Important: extra='allow'"
    Thanks to `extra="allow"` in the Pydantic model `ExecutionConfig`, all user attributes or additional fields from YAML are automatically saved and accessible through object attributes.

### LLM Adapter

Client for interacting with LLM API. Used for all requests to the language model.
Existing agents use the `openai-python` client.


### Streaming_generator — Streaming Module

The module's purpose is to register events occurring in the system and output results as the agent works.
Provides streaming responses from the agent in a format compatible with OpenAI API.

The standard implementation includes an OpenAI-like streaming protocol as a compromise-universal solution for compatibility. Depending on your system's needs, this module should be redesigned for a more convenient/concise format.


To receive the stream, use an async iterator. Events will be added as they are added to the generator:
```python
async for chunk in agent.streaming_generator:
    print(chunk, end="")
```

### _context — Execution Context

Stores agent state, data, counters, and execution results.

```python
# Main fields:
state                    # Current agent state identifier
iteration                # Current iteration number
clarifications_used      # Number of clarification requests made
execution_result         # Final agent execution result
custom_context           # Section for any user data
```
### toolkit — Tool Set

List of tool classes available to the agent for performing actions.

```python
self.toolkit: list[Type[BaseTool]]

# Example tool set:
self.toolkit = [
    WebSearchTool,
    ExtractPageContentTool,
    CreateReportTool,
    FinalAnswerTool
]

# Usage in _prepare_tools():
tools = set(self.toolkit)
# Filtering tools based on state
if self._context.searches_used >= self.config.search.max_searches:
    tools -= {WebSearchTool}
```

### conversation — Conversation History

List of messages in OpenAI format for maintaining conversation context with LLM.

```python
conversation: list[dict]

# Message format:
conversation = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {
        "role": "assistant",
        "content": "...",
        "tool_calls": [{"type": "function", "id": "...", "function": {...}}]
    },
    {"role": "tool", "content": "...", "tool_call_id": "..."}
]
```

## Examples of Using Custom Agents

### Example 1: Research Agent with _prepare_tools Override

`ResearchSGRAgent` demonstrates how to override `_prepare_tools()` for dynamic tool management based on agent state:

```python
from typing import Type
from sgr_agent_core.agents import SGRAgent
from sgr_agent_core.tools import (
    ClarificationTool,
    CreateReportTool,
    FinalAnswerTool,
    WebSearchTool,
)
from sgr_agent_core.next_step_tool import NextStepToolsBuilder, NextStepToolStub

class ResearchSGRAgent(SGRAgent):

    async def _prepare_tools(self) -> Type[NextStepToolStub]:
        tools = set(self.toolkit)

        if self._context.iteration >= self.config.execution.max_iterations:  # (1)!
            tools = {
                CreateReportTool,
                FinalAnswerTool,
            }

        if self._context.clarifications_used >= self.config.execution.max_clarifications:  # (2)!
            tools -= {ClarificationTool}

        if self._context.searches_used >= self.config.search.max_searches:  # (3)!
            tools -= {WebSearchTool}

        return NextStepToolsBuilder.build_NextStepTools(list(tools))
```

1. If iteration limit is reached, keep only final tools for completion
2. If clarifications are exhausted, remove `ClarificationTool` from available tools
3. If searches are exhausted, remove `WebSearchTool` from available tools

!!! Tip "State Machine for Tool Management... Or Something More"
    For more complex tool management logic, you can use a more serious state engine. This will allow you to explicitly define agent states and transition rules, simplifying the management of available tools at each stage of work.

### Example 2: Data Analysis Agent

```python
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import BaseTool, FinalAnswerTool
from sgr_agent_core.tools.reasoning_tool import ReasoningTool

class DataAnalysisTool(BaseTool):
    """Tool for data analysis."""
    tool_name: str = "data_analysis"
    description: str = "Analyzes provided data"

    data: str

    async def __call__(self, context, config, **kwargs) -> str:
        # Data analysis logic
        return f"Analysis result for: {self.data}"

class DataAnalysisAgent(BaseAgent):
    """Agent for data analysis."""

    name: str = "data_analysis_agent"

    async def _select_action_phase(self, reasoning):
        if "analyze" in reasoning.remaining_steps:
            return DataAnalysisTool(data=self.task)
        return FinalAnswerTool(answer="Analysis complete")

    async def _action_phase(self, tool):
        result = await tool(self._context, self.config)
        if isinstance(tool, FinalAnswerTool):
            self._context.execution_result = result
            self._context.state = AgentStatesEnum.COMPLETED
        return result
```


## General Recommendations

!!! Tip "Important Points"

    - **Inherit from ready-made agents**: Use `SGRAgent` or `ToolCallingAgent` as base classes instead of `BaseAgent` if you don't need full customization

    - **Agent registration**: Make sure your custom agent is imported into the project or YAML configuration before using it through `AgentFactory`

    - **Asynchronicity**: All methods for working with LLM and tools must be asynchronous

    - **Context memory**: `conversation` accumulates during execution, monitor its size and content to avoid degradation in LLM generation quality
