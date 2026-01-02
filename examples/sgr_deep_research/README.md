# SGR Deep Research

Research agents configuration for SGR Agent Core. This package provides pre-configured research agents with web search, content extraction, and reporting capabilities.

## Description

SGR Deep Research contains research agent definitions and configuration files for running deep research tasks. The agents are based on the SGR Agent Core framework and include:

- **SGR Agent** - Schema-Guided Reasoning agent for structured research
- **Tool Calling Agent** - Function calling agent for research tasks
- **SGR Tool Calling Agent** - Hybrid SGR + function calling agent

All agents include:

- Web search capabilities (Tavily)
- Content extraction from web pages
- Report generation
- Clarification requests
- Plan generation and adaptation

## Installation

Make sure you have `sgr-agent-core` installed:

```bash
pip install sgr-agent-core
```

## Configuration

1. Copy `config.yaml` and fill in your API keys:

```bash
cp config.yaml my_config.yaml
```

2. Edit `my_config.yaml` and set:
   - `llm.api_key` - Your OpenAI API key
   - `search.tavily_api_key` - Your Tavily API key (optional, if using search)

## Usage

### Running the API Server

To run the SGR Agent Core API server with research agents from this configuration, use the `sgr` utility:

```bash
sgr --config-file examples/sgr_deep_research/config.yaml
```

> **Note:** You can also run the server directly with Python:
>
> ```bash
> python -m sgr_agent_core.server --config-file examples/sgr_deep_research/config.yaml
> ```

### Using Python API

```python
import asyncio
from pathlib import Path

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_factory import AgentFactory
from definitions import get_research_agents_definitions

# Load configuration
config_path = Path(__file__).parent / "config.yaml"
config = GlobalConfig.from_yaml(str(config_path))

# Add research agents
config.agents.update(get_research_agents_definitions())

# Get agent definition
agent_def = config.agents["sgr_agent"]


# Create and run agent
async def main():
    agent = await AgentFactory.create(agent_def, task="Research AI trends in 2024")

    async for chunk in agent.stream():
        print(chunk, end="", flush=True)

    result = await agent.execute()
    print(f"\n\nFinal result: {result}")


asyncio.run(main())
```

### Using OpenAI-compatible API

If you're running the SGR Agent Core API service, you can use these agents by specifying the agent name in your request:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8010/v1",
    api_key="dummy",
)

response = client.chat.completions.create(
    model="sgr_tool_calling_agent",  # Use agent name from config
    messages=[{"role": "user", "content": "Research AI trends in 2024"}],
    stream=True,
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Available Agents

### sgr_agent

Schema-Guided Reasoning agent that uses structured reasoning phases:

- Reasoning phase: Analyzes task and generates plan
- Action phase: Executes tools based on reasoning

### tool_calling_agent

Function calling agent that uses OpenAI's function calling:

- Direct tool selection via function calls
- Faster execution for simple tasks

### sgr_tool_calling_agent

Hybrid agent combining SGR reasoning with function calling:

- Reasoning phase for complex planning
- Function calling for tool execution
- Best balance of structure and flexibility

## Agent Configuration

### Relative Imports

The `base_class` field in agent definitions supports relative imports. When the config file is located in the same directory or subdirectory as your agent classes, you can use relative paths:

```yaml
agents:
  sgr_agent:
    base_class: "agents.ResearchSGRAgent"  # Relative to config.yaml location
```

Instead of the full path:

```yaml
agents:
  sgr_agent:
    base_class: "examples.sgr_deep_research.agents.ResearchSGRAgent"  # Absolute path
```

The system automatically resolves relative imports based on the location of the config.yaml file.

## Configuration Options

### LLM Settings

- `api_key`: OpenAI API key (required)
- `base_url`: API base URL (default: "https://api.openai.com/v1")
- `model`: Model name (default: "gpt-4o-mini")
- `temperature`: Generation temperature (default: 0.4)
- `max_tokens`: Maximum output tokens (default: 8000)
- `proxy`: Optional proxy URL (socks5:// or http://)

### Search Settings

- `tavily_api_key`: Tavily API key (required for search)
- `max_searches`: Maximum search operations (default: 4)
- `max_results`: Maximum results per search (default: 10)
- `content_limit`: Character limit per source (default: 1500)

### Execution Settings

- `max_clarifications`: Maximum clarification requests (default: 3)
- `max_iterations`: Maximum agent iterations (default: 10)
- `logs_dir`: Directory for execution logs (default: "logs")
- `reports_dir`: Directory for research reports (default: "reports")

## Tools

All research agents include the following tools:

- **WebSearchTool** - Search the web using Tavily
- **ExtractPageContentTool** - Extract content from web pages
- **CreateReportTool** - Generate research reports
- **FinalAnswerTool** - Provide final answers
- **ClarificationTool** - Request clarifications from user
- **GeneratePlanTool** - Generate research plans
- **AdaptPlanTool** - Adapt plans based on findings
- **ReasoningTool** - Structured reasoning (SGR agents only)

## Notes

- Agents automatically manage tool availability based on execution state
- Reports are saved to `reports_dir` when `CreateReportTool` is used
- Execution logs are saved to `logs_dir` for debugging
- All agents support streaming responses via the API
