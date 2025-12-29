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

Example:

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

The tool will be automatically registered and available for use in agent configurations.

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
  max_iterations: 10  # After this limit, only FinalAnswerTool and CreateReportTool are available
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

```yaml
search:
  tavily_api_key: "your-tavily-api-key"  # Required: Tavily API key
  tavily_api_base_url: "https://api.tavily.com"  # Tavily API URL
  max_searches: 4  # Maximum number of search operations
  max_results: 10  # Maximum results in search query (overrides tool's max_results if lower)
```

After reaching `max_searches`, the tool is automatically removed from available tools.

**Example:**

```yaml
agents:
  research_agent:
    search:
      max_searches: 6
      max_results: 15
    tools:
      - "WebSearchTool"
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
Call after WebSearchTool to get detailed information from promising URLs found in search results.

**Important Warnings:**

- Extracted pages may show data from DIFFERENT years/time periods than asked
- ALWAYS verify that extracted content matches the question's temporal context
- If extracted content contradicts search snippet, prefer snippet for factual questions
- For date/number questions, cross-check extracted values with search snippets

**Configuration:**

```yaml
search:
  tavily_api_key: "your-tavily-api-key"  # Required: Tavily API key
  tavily_api_base_url: "https://api.tavily.com"  # Tavily API URL
  content_limit: 1500  # Content character limit per source (truncates extracted content)
```

**Example:**

```yaml
agents:
  research_agent:
    search:
      content_limit: 2000  # Increase content limit for more detailed extraction
    tools:
      - "WebSearchTool"
      - "ExtractPageContentTool"
```

## Tool Configuration in Agents

Tools are configured per agent in the `agents.yaml` file or agent definitions:

```yaml
agents:
  my_agent:
    base_class: "SGRAgent"
    tools:
      - "WebSearchTool"
      - "ExtractPageContentTool"
      - "CreateReportTool"
      - "ClarificationTool"
      - "GeneratePlanTool"
      - "AdaptPlanTool"
      - "FinalAnswerTool"
    execution:
      max_clarifications: 3
      max_iterations: 10
    search:
      max_searches: 4
      max_results: 10
      content_limit: 1500
```

### Tool Availability Control

Agents automatically filter available tools based on execution limits:

- After `max_iterations`: Only `CreateReportTool` and `FinalAnswerTool` are available
- After `max_clarifications`: `ClarificationTool` is removed
- After `max_searches`: `WebSearchTool` is removed

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

## Default Toolset

The default toolkit includes all standard tools:

**Source:** [sgr_deep_research/default_definitions.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_deep_research/default_definitions.py)

```python
DEFAULT_TOOLKIT = [
    ClarificationTool,
    GeneratePlanTool,
    AdaptPlanTool,
    FinalAnswerTool,
    WebSearchTool,
    ExtractPageContentTool,
    CreateReportTool,
]
```

ReasoningTool is added separately for SGR-based agents that require explicit reasoning phases.
