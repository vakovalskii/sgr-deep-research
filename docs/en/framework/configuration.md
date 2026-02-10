# Configuration Guide

This guide describes the SGR Agent Core configuration system and ways to configure agents for your project.

## Hierarchy

The configuration system is built on the principle of extension:
Common settings from the main config override defaults,
and specific settings from `agents` override necessary parameters for each specific agent at the `AgentDefinition` level.

```mermaid
graph TD
    FD[Framework Defaults]
    B[.env]
    C[config.yaml]
    A[any other definitions yaml]
    D[agents.yaml]
    E[GlobalConfig]
    G[Agent Config]
    I[AgentDefinition]
    J[Agent]

    FD ----> E
    B ---> E
    C --> E
    D --> G
    A --> G
    E --> I
    G --> I
    I --> J

    style E fill:#10B981
    style G fill:#10B981
    style I fill:#8B5CF6
    style J fill:#8B5CF6
```

## GlobalConfig

!!! Important "Important: Single GlobalConfig Instance"
    All calls to `GlobalConfig()` return the same instance. This means that when creating multiple `GlobalConfig` objects, you will get a reference to the same object in memory.

    Once applied changes and loaded configurations will propagate throughout the program.

### Loading from Environment Variables (.env)

`GlobalConfig` uses `pydantic-settings` to automatically load settings from environment variables. All variables must have the `SGR__` prefix and use double underscores `__` for nested parameters.

```python
from sgr_agent_core import GlobalConfig

config = GlobalConfig()
```

An example can be found in [`.env.example`](https://github.com/vamplabAI/sgr-agent-core/blob/main/.env.example).

### Loading from YAML File

For more structured configuration, you can use YAML files:

```python
from sgr_agent_core import GlobalConfig

# Load from config.yaml
config = GlobalConfig.from_yaml("config.yaml")
```

An example can be found in [`config.yaml.example`](https://github.com/vamplabAI/sgr-agent-core/blob/main/config.yaml.example).

### Parameter Override

**Key Feature:** `AgentDefinition` inherits all parameters from `GlobalConfig` and overrides only those explicitly specified. This allows creating minimal configurations by specifying only necessary changes.

### Tool Definitions

Tools can be defined in a separate `tools:` section in `config.yaml` or `agents.yaml`. This allows you to:
- Define custom tools with specific configurations
- Reference tools by name in agent definitions
- Override default tool classes

**Tool Definition Format:**

Each entry in the global `tools:` section can include:

- **base_class** (optional) – import path or registry name for the tool class
- **Any other keys** – passed to the tool at runtime as kwargs (e.g. `max_results`, `max_searches`, `content_limit` for search tools). Agents that reference the tool by name receive these params; per-agent inline config in the `tools` list overrides global values.

```yaml
tools:
  # Simple tool definition (uses default base_class from ToolRegistry)
  reasoning_tool:
    # base_class defaults to sgr_agent_core.tools.ReasoningTool

  # Custom tool with explicit base_class
  custom_tool:
    base_class: "tools.CustomTool"  # Relative import path

  # Global defaults for a tool (all agents using this tool by name get these kwargs)
  web_search_tool:
    max_results: 12
    max_searches: 6
```

**Using Tools in Agents:**

Each item in the `tools` list can be:

- **String** – tool name (resolved from the `tools:` section or `ToolRegistry`)
- **Object** – dict with required `"name"` and optional parameters passed to the tool at runtime as kwargs (e.g. search settings for search tools)

```yaml
agents:
  my_agent:
    base_class: "SGRToolCallingAgent"
    tools:
      - "web_search_tool"
      - "reasoning_tool"
      # Per-tool config: name + kwargs (e.g. search settings)
      - name: "extract_page_content_tool"
        content_limit: 2000
      - name: "web_search_tool"
        max_results: 15
        max_searches: 6
        # tavily_api_key, max_searches, etc. can be set here instead of in global search:
```

Search-related settings (`tavily_api_key`, `tavily_api_base_url`, `max_results`, `content_limit`, `max_searches`) can be set globally in `search:` or per-tool in the tool object. Tool kwargs override agent-level `search` for that tool.

!!! note "Tool Resolution Order"
    When resolving tools, the system checks in this order:
    1. Tools defined in `tools:` section (by name)
    2. Tools registered in `ToolRegistry` (by snake_case name - recommended, or PascalCase class name for backward compatibility)
    3. Auto-conversion from snake_case to PascalCase (e.g., `web_search_tool` → `WebSearchTool`) for backward compatibility

### Agent Configuration Examples

Agents are defined in the `agents.yaml` file or can be loaded programmatically:

```python
from sgr_agent_core import GlobalConfig

config = GlobalConfig.from_yaml("config.yaml")
config.definitions_from_yaml("agents.yaml")
config.definitions_from_yaml("more_agents.yaml")
```

!!!warning
    The `definitions_from_yaml` method merges new definitions with existing ones, overwriting agents with the same names

#### Example 1: Minimal Configuration

An agent that overrides only the LLM model and toolset:

```yaml
agents:
  simple_agent:
    base_class: "SGRToolCallingAgent"

    # Override only the model
    llm:
      model: "gpt-4o-mini"

    # Specify minimal toolset
    tools:
      - "web_search_tool"
      - "final_answer_tool"
```

In this example, the `simple_agent` uses:

- All LLM settings from `GlobalConfig`, except `model`
- All search settings from `GlobalConfig`
- All execution settings from `GlobalConfig`
- Only the two specified tools

#### Example 2: Full Customization

An agent with full parameter override:

```yaml
agents:
  custom_research_agent:
    base_class: "sgr_agent_core.agents.sgr_agent.ResearchSGRAgent"

    # Override LLM settings
    llm:
      model: "gpt-4o"
      temperature: 0.3
      max_tokens: 16000
      # api_key and base_url are inherited from GlobalConfig

    # Override search settings
    search:
      max_results: 15
      max_searches: 6
      content_limit: 2000

    # Override execution settings
    execution:
      max_iterations: 15
      max_clarifications: 5
      max_searches: 6
      streaming_generator: "openai"  # default; use "open_webui" for Open WebUI UI
      logs_dir: "logs/custom_agent"
      reports_dir: "reports/custom_agent"

    # Full toolset
    tools:
      - "web_search_tool"
      - "extract_page_content_tool"
      - "create_report_tool"
      - "clarification_tool"
      - "generate_plan_tool"
      - "adapt_plan_tool"
      - "final_answer_tool"
```

#### Example 3: Speed-Optimized

An agent with settings for fast execution:

```yaml
agents:
  fast_research_agent:
    base_class: "SGRToolCallingAgent"

    llm:
      model: "gpt-4o-mini"
      temperature: 0.1  # More deterministic responses
      max_tokens: 4000  # Fewer tokens for faster response

    execution:
      max_iterations: 8  # Fewer iterations
      max_clarifications: 2
      max_searches: 3

    tools:
      - "web_search_tool"
      - "create_report_tool"
      - "final_answer_tool"
      - "reasoning_tool"
```

#### Example 4: Streaming generator (openai / open_webui)

Choose the streaming response format via `execution.streaming_generator`. Built-in options are resolved from `StreamingGeneratorRegistry`:

- `openai` (default) — OpenAI SSE format; universal compatibility.
- `open_webui` — Open WebUI format with `<details>` blocks for tool calls and results (e.g. for UIs that render markdown).

```yaml
agents:
  open_webui_agent:
    base_class: "SGRToolCallingAgent"

    llm:
      model: "gpt-4o-mini"

    execution:
      streaming_generator: "open_webui"

    tools:
      - "web_search_tool"
      - "final_answer_tool"
      - "reasoning_tool"
```

Custom generators can be registered in code; then use their registry name in config.

#### Example 5: With Custom Prompts

An agent with system prompt override:

```yaml
agents:
  technical_analyst:
    base_class: "SGRAgent"

    llm:
      model: "gpt-4o"
      temperature: 0.2

    # Override prompts
    prompts:
      system_prompt_str: |
        You are a highly specialized technical analyst.
        Your expertise includes deep technical analysis and
        detailed research documentation.

    execution:
      max_iterations: 20
      max_searches: 8

    tools:
      - "web_search_tool"
      - "extract_page_content_tool"
      - "create_report_tool"
      - "clarification_tool"
      - "final_answer_tool"
```

#### Example 6: With Tool Definitions

An agent using custom tool definitions:

```yaml
# Define tools in tools section
tools:
  reasoning_tool:
    # Uses default: sgr_agent_core.tools.ReasoningTool
  custom_file_tool:
    base_class: "tools.CustomFileTool"  # Custom tool from local module

agents:
  file_agent:
    base_class: "SGRToolCallingAgent"

    llm:
      model: "gpt-4o-mini"

    # Reference tools by name from tools section or ToolRegistry
    tools:
      - "reasoning_tool"  # From tools section
      - "custom_file_tool"  # From tools section
      - "final_answer_tool"  # From ToolRegistry
```

## Recommendations

- **Store secrets in .env** - don't commit sensitive keys to the repository =)

  In production environments, it's recommended to use ENV variables instead of hardcoding keys in YAML

- **Use minimal overrides** - specify only what differs from GlobalConfig

- **Store Definitions, not Agents** - Agents are created for direct task execution,
  their definitions can be added/removed/modified at any time
