# Agents with Disabled Reporting

This directory contains versions of research agents that exclude `CreateReportTool` from their toolkit. These agents work identically to their standard counterparts but do not generate report files.

## Available Agents

- **ResearchSGRAgentNoReporting** - SGR agent without reporting
- **ResearchToolCallingAgentNoReporting** - Tool calling agent without reporting
- **ResearchSGRToolCallingAgentNoReporting** - SGR tool calling agent without reporting

## Installation

Make sure you have `sgr_agent_core` installed:

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

To run the SGR Deep Research API server with agents from this directory:

```bash
sgr --config-file examples/agents_with_disabled_reporting/config.yaml
```

### Using Python API

```python
import asyncio
from pathlib import Path

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agent_definition import AgentDefinition

# Load configuration
config_path = Path(__file__).parent / "config.yaml"
GlobalConfig.load_from_yaml(str(config_path))

# Get agent definition
agent_def = GlobalConfig().agents["sgr_agent_no_reporting"]


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

If you're running the SGR Deep Research API service, you can use these agents by specifying the agent name in your request:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8010/v1",
    api_key="dummy",
)

response = client.chat.completions.create(
    model="sgr_agent_no_reporting",  # Use agent name from config
    messages=[{"role": "user", "content": "Research AI trends in 2024"}],
    stream=True,
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

## Differences from Standard Agents

The agents in this directory are identical to their standard counterparts except:

1. **No CreateReportTool** - These agents do not include `CreateReportTool` in their toolkit
2. **No report files** - Agents will not generate report files in the `reports_dir`
3. **FinalAnswerTool only** - When `max_iterations` is reached, only `FinalAnswerTool` is available (standard agents also have `CreateReportTool`)

## Notes

- These agents still use all other tools (WebSearchTool, ExtractPageContentTool, FinalAnswerTool, etc.)
- The `reports_dir` setting in config is ignored since no reports are generated
- All other functionality remains the same as standard agents
