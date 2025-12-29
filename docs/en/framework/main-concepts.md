# Main Concepts

This document describes the key entities of the SGR Deep Research Framework.

![SGR Agent Core Concept](../../assets/images/sgr_concept.png)

## Vibe Glossary

**Large Language Model (LLM)** — a large language model trained on vast amounts of data to generate and understand text. In the framework context, used for reasoning, planning, and action selection by the agent.

**Structured Output (SO)** — an approach to obtaining structured data from LLM through explicit JSON schema definition. Instead of a free-form text response, the model returns data in a strictly defined format, ensuring reliable parsing and validation. In the framework, used via the `response_format` parameter.

**Function Calling (FC)** — native mechanism for calling functions/tools. LLM receives descriptions of available functions and can explicitly request their invocation, returning structured arguments. Allows integration of external tools and APIs into the model dialogue. In most inference engines and LLM API providers, the backend used for generating JSON schemas is identical to Structured Output.

**Reasoning** — the process of reasoning and analysis during which the agent evaluates the current situation, analyzes available information, plans next steps, and makes decisions about action selection. In the framework, reasoning can be explicit (through structured schema) or implicit (within LLM).

**Tool** — an executable component that the agent can invoke to perform specific actions (web search, clarification requests, report creation, etc.).

**Agent** — an autonomous software entity capable of perceiving the environment, making decisions, and performing actions to achieve a set goal. In the framework, the agent implements a Reasoning → Action cycle, using LLM for decision-making and tools for action execution.

## Agent

**BaseAgent** — Parent class for all agents. Defines a two-phase execution cycle: Reasoning Phase → (Select Action Phase + Call Action Phase)

From a program logic perspective, one could say there are three phases, but Call Action, strictly speaking, is not an agent action — it delegates the task to a tool, so it seems simpler and more familiar to perceive it as a ReAct execution cycle. </br>
The practical number of actions and LLM requests can vary significantly depending on specific implementations.

All created agents are automatically registered in `AgentRegistry`

??? example "BaseAgent in detail"
    *For understanding the full logic, it's better to familiarize yourself with the [source code](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_agent.py).*


    Simplified representation of the main work cycle:
    ```py
    while agent.state not in FINISH_STATES:
        reasoning = await agent._reasoning_phase()
        action_tool = await agent._select_action_phase(reasoning)
        await agent._action_phase(action_tool)
    ```


    In base_agent, a minimal interface is provided for modifying agent behavior and working with context.
    When creating custom solutions, pay attention first and foremost to these methods
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
    ```

### Available Agents

The framework includes several ready-made agent implementations:

#### SGRAgent

**Schema-Guided Reasoning Agent** — fully based on the Structured Output approach. </br>
Performs well for models that struggle with Reasoning / Function Calling on their own.

- **Reasoning Phase**: A dynamic JSON schema is created containing descriptions of all available tools.
 LLM returns a response that, in addition to reasoning, contains a ready tool schema in the `function` field
- **Select Action Phase**: The tool is extracted directly from `reasoning.function` — LLM has already selected the tool in the reasoning phase
- **Action Phase**: Standard execution of the selected tool


#### ToolCallingAgent

**Native Function Calling Agent** — relies on native function calling without an explicit reasoning phase.
Modern models are sufficiently independent and were specifically trained for this format of work, and limiting their reasoning capabilities
may only hinder them. </br>
Performs best when working with large, "smart" models

- **Reasoning Phase**: Absent — reasoning occurs inside LLM
- **Select Action Phase**: Uses `tool_choice="required"` to force tool invocation inside LLM
- **Action Phase**: Standard execution of the selected tool

#### SGRToolCallingAgent

**Hybrid SGR + Function Calling Agent** — combines structured reasoning with native function calling.
Takes the best of both worlds. Performs well for most tasks

- **Reasoning Phase**: Uses function calling to obtain the result of the system `ReasoningTool` (explicit reasoning through structured schema)
- **Select Action Phase**: Uses function calling with `tool_choice="required"` to select a specific tool based on the reasoning phase context
- **Action Phase**: Standard execution of the selected tool

#### ResearchSGRAgent
#### ResearchToolCallingAgent
#### ResearchSGRToolCallingAgent

More applied agent implementations for working with information, having a predefined set of tools


## Tool

**BaseTool** — Parent class for all tools. Represents a Pydantic model.</br>
A tool is a single entry point for any agent behavior logic — the set of tools defines its capabilities and specificity.

All created tools are automatically registered in `ToolRegistry`

### Tool Components

- **`tool_name`** — name. Used to identify the tool in the system and when calling through LLM.

- **`description`** — description and instructions. Used by LLM to understand the tool's purpose and capabilities. If not explicitly specified, automatically taken from the class docstring.

- **`__call__()`** — Main method for invoking tool logic by the agent.

### MCPTool

**MCPBaseTool** — Base class for tools integrated with MCP (Model Context Protocol) servers. Handles calls through MCP client, converts them to the framework tool format

!!!tip
    *For more details on tools and their usage: [Tools](tools.md)*

## Definition

**AgentDefinition** — Template for creating agents. Contains all necessary configuration for building an instance for a specific task.
By general idea we have:
Agent - Universal implementation of main agent logic methods
Definition - Schema and values of agent settings.
Agent object - Agent+Definition: Ready agent with isolated context, history, logs, and executing a specific task

## AgentConfig

**AgentConfig** — centralized agent configuration combining LLM, search, execution, prompts, and MCP settings. Supports hierarchical configuration system through `GlobalConfig` and `AgentDefinition` with automatic parameter inheritance and override.
!!!tip
    *For more details on configuration and definitions: [Configuration Guide](configuration.md)*


## Registry

**Registry** — centralized registries (`AgentRegistry`, `ToolRegistry`) for automatic registration and class lookup.
