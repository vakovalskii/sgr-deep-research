# Tools Documentation

This document describes all available tools in the SGR Deep Research framework, their parameters, behavior, and configuration options.

## Tool Categories

Tools are divided into two categories:

**System Tools** - Essential tools required for deep research functionality. Without these, the research agent cannot function properly:

- ReasoningTool
- FinalAnswerTool
- CreateReportTool
- ClarificationTool
- GeneratePlanTool
- AdaptPlanTool

**Auxiliary Tools** - Optional tools that extend agent capabilities but are not strictly required:

- WebSearchTool
- ExtractPageContentTool

## BaseTool

All tools inherit from `BaseTool`, which provides the foundation for tool functionality.

**Source:** [sgr_agent_core/base_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_tool.py)

### BaseTool Class

```python
class BaseTool(BaseModel, ToolRegistryMixin):
    tool_name: ClassVar[str] = None
    description: ClassVar[str] = None

    async def __call__(
        self, context: AgentContext, config: AgentConfig, **kwargs
    ) -> str:
        raise NotImplementedError("Execute method must be implemented by subclass")
```

### Key Features

- **Automatic Registration**: Tools are automatically registered in `ToolRegistry` when defined
- **Pydantic Model**: All tools are Pydantic models, enabling validation and serialization
- **Async Execution**: Tools execute asynchronously via the `__call__` method
- **Context Access**: Tools receive `ResearchContext` and `AgentConfig` for state and configuration access

### Creating Custom Tools

To create a custom tool:

1. Inherit from `BaseTool`
2. Define tool parameters as Pydantic fields
3. Implement the `__call__` method
4. Optionally set `tool_name` and `description` class variables

**Example: Basic Custom Tool**

```python
from sgr_agent_core.base_tool import BaseTool
from pydantic import Field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext


class CustomTool(BaseTool):
    """Description of what this tool does."""

    tool_name = "customtool"  # Optional, auto-generated from class name if not set

    reasoning: str = Field(description="Why this tool is needed")
    parameter: str = Field(description="Tool parameter")

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        # Tool implementation
        result = f"Processed: {self.parameter}"
        return result
```

The tool will be automatically registered in `ToolRegistry` when the class is defined and can be used in agent configurations.

### Using Custom Tools in Configuration

Once you've created a custom tool, you can use it in your configuration in two ways:

**Method 1: Direct Reference (if tool is imported and registered)**

If your custom tool is imported before agent creation, it will be automatically registered and can be referenced by name:

```yaml
agents:
  my_agent:
    base_class: "SGRToolCallingAgent"
    tools:
      - "custom_tool"  # Direct reference to registered tool
      - "web_search_tool"
```

**Method 2: Define in tools section with base_class**

You can define custom tools in the `tools:` section and specify the `base_class`:

```yaml
tools:
  # Custom tool with explicit base_class
  custom_tool:
    base_class: "tools.CustomTool"  # Relative import path
    # Or use full path:
    # base_class: "my_package.tools.CustomTool"

agents:
  my_agent:
    base_class: "SGRToolCallingAgent"
    tools:
      - "custom_tool"  # Reference by name from tools section
      - "web_search_tool"
```

**Important Notes:**

- Custom tools must be imported before agent creation to be automatically registered
- When using `base_class` in tool definitions, you can use:
  - Relative import paths (e.g., `"tools.CustomTool"`) - resolved relative to the config file location
  - Full import paths (e.g., `"my_package.tools.CustomTool"`) - resolved from Python's `sys.path`
  - Class names (e.g., `"CustomTool"`) - resolved from `ToolRegistry`
- Tools defined in the `tools:` section take precedence over tools in `ToolRegistry`

## System Tools

### ReasoningTool

**Type:** System Tool
**Source:** [sgr_agent_core/tools/reasoning_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/reasoning_tool.py)

Core tool for Schema-Guided Reasoning agents. Determines the next reasoning step with adaptive planning capabilities.

**Parameters:**

- `reasoning_steps` (list\[str\], 2-3 items): Step-by-step reasoning process
- `current_situation` (str, max 300 chars): Current research situation assessment
- `plan_status` (str, max 150 chars): Status of current plan
- `enough_data` (bool, default=False): Whether sufficient data is collected
- `remaining_steps` (list\[str\], 1-3 items): Remaining action steps
- `task_completed` (bool): Whether the research task is finished

**Behavior:**
Returns JSON representation of reasoning state. Used by SGR agents to structure their decision-making process.

**Usage:**
Required tool for SGR-based agents. Must be used before any other tool execution in the reasoning phase.

**Configuration:**
No specific configuration required. Tool behavior is controlled by agent prompts and LLM settings.

### FinalAnswerTool

**Type:** System Tool
**Source:** [sgr_agent_core/tools/final_answer_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/final_answer_tool.py)

Finalizes research task and completes agent execution.

**Parameters:**

- `reasoning` (str): Why task is complete and how answer was verified
- `completed_steps` (list\[str\], 1-5 items): Summary of completed steps including verification
- `answer` (str): Comprehensive final answer with exact factual details
- `status` (Literal\["completed", "failed"\]): Task completion status

**Behavior:**

- Sets `context.state` to the specified status
- Stores `answer` in `context.execution_result`
- Returns JSON representation of the final answer

**Usage:**
Call after completing a research task to finalize execution.

**Configuration:**
No specific configuration required.

**Example:**

```yaml
execution:
  max_iterations: 10  # After this limit, only final_answer_tool and create_report_tool are available
```

### CreateReportTool

**Type:** System Tool
**Source:** [sgr_agent_core/tools/create_report_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/create_report_tool.py)

Creates a comprehensive detailed report with citations as the final step of research.

**Parameters:**

- `reasoning` (str): Why ready to create report now
- `title` (str): Report title
- `user_request_language_reference` (str): Copy of original user request for language consistency
- `content` (str): Comprehensive research report with inline citations \[1\], \[2\], \[3\]
- `confidence` (Literal\["high", "medium", "low"\]): Confidence level in findings

**Behavior:**

- Saves report to file in `config.execution.reports_dir`
- Filename format: `{timestamp}_{safe_title}.md`
- Includes full content with sources section
- Returns JSON with report metadata (title, content, confidence, sources_count, word_count, filepath, timestamp)

**Usage:**
Final step after collecting sufficient research data.

**Configuration:**

```yaml
execution:
  reports_dir: "reports"  # Directory for saving reports
```

**Important:**

- Every factual claim in content MUST have inline citations \[1\], \[2\], \[3\]
- Citations must be integrated directly into sentences
- Content must use the same language as `user_request_language_reference`

### ClarificationTool

**Type:** System Tool
**Source:** [sgr_agent_core/tools/clarification_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/clarification_tool.py)

Asks clarifying questions when facing an ambiguous request.

**Parameters:**

- `reasoning` (str, max 200 chars): Why clarification is needed (1-2 sentences MAX)
- `unclear_terms` (list\[str\], 1-3 items): List of unclear terms (brief, 1-3 words each)
- `assumptions` (list\[str\], 2-3 items): Possible interpretations (short, 1 sentence each)
- `questions` (list\[str\], 1-3 items): Specific clarifying questions (short and direct)

**Behavior:**

- Returns questions as newline-separated string
- Pauses agent execution until clarification is received
- Sets agent state to `WAITING_FOR_CLARIFICATION`
- Increments `context.clarifications_used`

**Usage:**
Use when user request is ambiguous or requires additional information.

**Configuration:**

```yaml
execution:
  max_clarifications: 3  # Maximum number of user clarification requests
```

After reaching `max_clarifications`, the tool is automatically removed from available tools.

### GeneratePlanTool

**Type:** System Tool
**Source:** [sgr_agent_core/tools/generate_plan_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/generate_plan_tool.py)

Generates a research plan to split complex requests into manageable steps.

**Parameters:**

- `reasoning` (str): Justification for research approach
- `research_goal` (str): Primary research objective
- `planned_steps` (list\[str\], 3-4 items): List of planned steps
- `search_strategies` (list\[str\], 2-3 items): Information search strategies

**Behavior:**

- Returns JSON representation of the plan (excluding reasoning field)
- Used to structure complex research tasks

**Usage:**
Use at the beginning of research to break down complex requests.

**Configuration:**
No specific configuration required.

### AdaptPlanTool

**Type:** System Tool
**Source:** [sgr_agent_core/tools/adapt_plan_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/adapt_plan_tool.py)

Adapts a research plan based on new findings.

**Parameters:**

- `reasoning` (str): Why plan needs adaptation based on new data
- `original_goal` (str): Original research goal
- `new_goal` (str): Updated research goal
- `plan_changes` (list\[str\], 1-3 items): Specific changes made to plan
- `next_steps` (list\[str\], 2-4 items): Updated remaining steps

**Behavior:**

- Returns JSON representation of adapted plan (excluding reasoning field)
- Allows dynamic plan adjustment during research

**Usage:**
Use when initial plan needs modification based on discovered information.

**Configuration:**
No specific configuration required.

## Auxiliary Tools

### WebSearchTool

**Type:** Auxiliary Tool
**Source:** [sgr_agent_core/tools/web_search_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/web_search_tool.py)

Searches the web for real-time information using Tavily Search API.

**Parameters:**

- `reasoning` (str): Why this search is needed and what to expect
- `query` (str): Search query in same language as user request
- `max_results` (int, default=5, range 1-10): Maximum number of results to retrieve

**Behavior:**

- Executes search via TavilySearchService
- Adds found sources to `context.sources` dictionary
- Creates SearchResult and appends to `context.searches`
- Increments `context.searches_used`
- Returns formatted string with search query and results (titles, links, snippets)

**Usage:**
Use for finding up-to-date information, verifying facts, researching current events, technology updates, or any topic requiring recent information.

**Best Practices:**

- Use specific terms and context in queries
- For acronyms, add context: "SGR Schema-Guided Reasoning"
- Use quotes for exact phrases: "Structured Output OpenAI"
- Search queries in SAME LANGUAGE as user request
- For date/number questions, include specific year/context in query
- Search snippets often contain direct answers - check them carefully

**Configuration:**

Search settings are configured per-tool in the `tools:` section (not in a global `search:` block):

```yaml
tools:
  web_search_tool:
    tavily_api_key: "your-tavily-api-key"  # Required: Tavily API key
    tavily_api_base_url: "https://api.tavily.com"  # Tavily API URL
    max_searches: 4  # Maximum number of search operations
    max_results: 10  # Maximum results in search query (overrides tool's max_results if lower)
```

After reaching `max_searches`, the tool is automatically removed from available tools.

**Example:**

```yaml
tools:
  web_search_tool:
    tavily_api_key: "your-tavily-api-key"
    max_searches: 6
    max_results: 15

agents:
  research_agent:
    tools:
      - "web_search_tool"
```

### ExtractPageContentTool

**Type:** Auxiliary Tool
**Source:** [sgr_agent_core/tools/extract_page_content_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/extract_page_content_tool.py)

Extracts full detailed content from specific web pages using Tavily Extract API.

**Parameters:**

- `reasoning` (str): Why extract these specific pages
- `urls` (list\[str\], 1-5 items): List of URLs to extract full content from

**Behavior:**

- Extracts full content from specified URLs via TavilySearchService
- Updates existing sources in `context.sources` with full content
- For new URLs, adds them with sequential numbering
- Returns formatted string with extracted content preview (limited by `content_limit`)

**Usage:**
Call after `web_search_tool` to get detailed information from promising URLs found in search results.

**Important Warnings:**

- Extracted pages may show data from DIFFERENT years/time periods than asked
- ALWAYS verify that extracted content matches the question's temporal context
- If extracted content contradicts search snippet, prefer snippet for factual questions
- For date/number questions, cross-check extracted values with search snippets

**Configuration:**

Search settings are configured per-tool in the `tools:` section:

```yaml
tools:
  extract_page_content_tool:
    tavily_api_key: "your-tavily-api-key"  # Required: Tavily API key
    tavily_api_base_url: "https://api.tavily.com"  # Tavily API URL
    content_limit: 1500  # Content character limit per source (truncates extracted content)
```

**Example:**

```yaml
tools:
  extract_page_content_tool:
    tavily_api_key: "your-tavily-api-key"
    content_limit: 2000  # Increase content limit for more detailed extraction

agents:
  research_agent:
    tools:
      - "web_search_tool"
      - "extract_page_content_tool"
```

## Tool Configuration

### Configuring Tools in Agents

Tools are configured per agent in the `agents.yaml` file or agent definitions. You can reference tools in three ways:

1. **By name in snake_case** - Use snake_case format (e.g., `"web_search_tool"`) - **recommended**
2. **By name from tools section** - Define tools in a `tools:` section and reference them by name
3. **By PascalCase class name** - Use PascalCase format (e.g., `"WebSearchTool"`) - **for backward compatibility**

!!! note "Tool Naming"
    The recommended format is **snake_case** (e.g., `web_search_tool`). PascalCase format (e.g., `WebSearchTool`) is supported for backward compatibility but snake_case is preferred.

**Example: Basic Tool Configuration**

```yaml
tools:
  web_search_tool:
    tavily_api_key: "your-tavily-api-key"
    max_searches: 4
    max_results: 10
  extract_page_content_tool:
    tavily_api_key: "your-tavily-api-key"
    content_limit: 1500

agents:
  my_agent:
    base_class: "SGRAgent"
    tools:
      - "web_search_tool"
      - "extract_page_content_tool"
      - "create_report_tool"
      - "clarification_tool"
      - "generate_plan_tool"
      - "adapt_plan_tool"
      - "final_answer_tool"
    execution:
      max_clarifications: 3
      max_iterations: 10
```

### Defining Tools in Configuration

You can define tools in a separate `tools:` section in `config.yaml` or `agents.yaml`. This allows you to:

- Define custom tools with specific configurations
- Reference tools by name in agent definitions
- Override default tool classes using `base_class`

**Tool Definition Format:**

```yaml
tools:
  # Simple tool definition (uses default base_class from ToolRegistry)
  reasoning_tool:
    # base_class defaults to sgr_agent_core.tools.ReasoningTool

  # Custom tool with explicit base_class
  custom_tool:
    base_class: "tools.CustomTool"  # Relative import path or full path
    # Additional tool-specific parameters can be added here
```

**Using Defined Tools in Agents:**

```yaml
tools:
  reasoning_tool:
    # Uses default: sgr_agent_core.tools.ReasoningTool
  custom_file_tool:
    base_class: "tools.CustomFileTool"  # Custom tool from local module

agents:
  my_agent:
    base_class: "SGRToolCallingAgent"
    tools:
      - "reasoning_tool"  # From tools section
      - "custom_file_tool"  # From tools section
      - "web_search_tool"  # Recommended: snake_case format
      - "final_answer_tool"  # Recommended: snake_case format
```

!!! note "Tool Resolution Order"
    When resolving tools, the system checks in this order:
    1. Tools defined in `tools:` section (by name)
    2. Tools registered in `ToolRegistry` (by snake_case name - recommended, or PascalCase class name for backward compatibility)
    3. Auto-conversion from snake_case to PascalCase (e.g., `web_search_tool` → `WebSearchTool`) for backward compatibility

### Tool Availability Control

Agents automatically filter available tools based on execution limits:

- After `max_iterations`: Only `create_report_tool` and `final_answer_tool` are available
- After `max_clarifications`: `clarification_tool` is removed
- After `max_searches`: `web_search_tool` is removed

This ensures agents complete tasks within configured limits.

## MCP Tools

Tools can also be created from MCP (Model Context Protocol) servers. These tools inherit from `MCPBaseTool` and are automatically generated from MCP server schemas.

**Source:** [sgr_agent_core/base_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_tool.py) (MCPBaseTool class)

**Configuration:**

```yaml
mcp:
  mcpServers:
    deepwiki:
      url: "https://mcp.deepwiki.com/mcp"
    your_server:
      url: "https://your-mcp-server.com/mcp"
      headers:
        Authorization: "Bearer your-token"
```

**Behavior:**

- MCP tools are automatically converted to BaseTool instances
- Tool schemas are generated from MCP server input schemas
- Execution calls MCP server with tool payload
- Response is limited by `execution.mcp_context_limit`

**Configuration:**

```yaml
execution:
  mcp_context_limit: 15000  # Maximum context length from MCP server response
```

## Tool Registry

All tools are automatically registered in `ToolRegistry` when defined. Tools can be referenced by name in agent configurations.

**Source:** [sgr_agent_core/services/registry.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/services/registry.py)

Tools are registered with their `tool_name` (auto-generated from class name if not specified). Custom tools must be imported before agent creation to be registered.

## Standard Tools

All standard tools are automatically registered in `ToolRegistry` when imported from `sgr_agent_core.tools`. The standard toolkit includes:

**System Tools:**
- `ReasoningTool` - For SGR-based agents that require explicit reasoning phases
- `ClarificationTool` - For requesting user clarifications
- `GeneratePlanTool` - For generating research plans
- `AdaptPlanTool` - For adapting research plans
- `FinalAnswerTool` - For providing final answers
- `CreateReportTool` - For creating research reports

**Auxiliary Tools:**
- `WebSearchTool` - For web search functionality
- `ExtractPageContentTool` - For extracting content from web pages

All these tools can be referenced by name in agent configurations (see [Tool Configuration](#tool-configuration) section above).
