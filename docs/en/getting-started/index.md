# SGR Agent Core

**SGR Agent Core** is an open-source agentic framework for building intelligent research agents using Schema-Guided Reasoning (SGR). The project provides a core library with an extendable `BaseAgent` interface implementing a three-phase architecture and multiple ready-to-use research agent implementations built on top of it.

The library includes extensible tools for search, reasoning, and clarification, real-time streaming responses, and an OpenAI-compatible REST API. Works with any OpenAI-compatible LLM, including local models for fully private research.

## Why use SGR Agent Core?

* **Schema-Guided Reasoning** — SGR combines structured reasoning with flexible tool selection
* **Multiple Agent Types** — Choose from `SGRAgent`, `ToolCallingAgent`, or `SGRToolCallingAgent`
* **Extensible Architecture** — Easy to create custom agents and tools
* **OpenAI-Compatible API** — Drop-in replacement for OpenAI API endpoints
* **Real-time Streaming** — Built-in support for streaming responses via SSE
* **Production Ready** — Battle-tested with comprehensive test coverage and Docker support

## Quick Start

### Running with Docker

The fastest way to get started is using Docker:

```bash
# Clone the repository
git clone https://github.com/vamplabai/sgr-agent-core.git
cd sgr-agent-core

# Create directories with write permissions for all
sudo mkdir -p logs reports
sudo chmod 777 logs reports

# Copy and edit the configuration file
cp examples/sgr_deep_research/config.yaml.example examples/sgr_deep_research/config.yaml
# Edit examples/sgr_deep_research/config.yaml and set your API keys

# Run the container
docker run --rm -i \
  --name sgr-agent \
  -p 8010:8010 \
  -v $(pwd)/examples/sgr_deep_research:/app/examples/sgr_deep_research:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  ghcr.io/vamplabai/sgr-agent-core:latest \
  --config-file /app/examples/sgr_deep_research/config.yaml \
  --host 0.0.0.0 \
  --port 8010
```

The API server will be available at `http://localhost:8010`. Interactive API documentation (Swagger UI) is available at `http://localhost:8010/docs`.

### Installation

If you want to use SGR Agent Core as a Python library (framework):

```bash
pip install sgr-agent-core
```

See the [Installation Guide](installation.md) for detailed instructions and the [Using as Library](../framework/first-steps.md) guide to get started.

### CLI Tool (`sgrsh`)

After installation, you can use the `sgrsh` command-line tool for interactive agent usage:

```bash
# Single query mode
sgrsh "Find the current Bitcoin price"

# With agent selection
sgrsh --agent sgr_agent "What is AI?"

# With custom config file
sgrsh -c config.yaml -a sgr_agent "Your query"

# Interactive chat mode (no query argument)
sgrsh
sgrsh -a sgr_agent
```

The `sgrsh` command:
- Automatically looks for `config.yaml` in the current directory
- Supports interactive chat mode for multiple queries
- Handles clarification requests from agents interactively
- Works with any agent defined in your configuration

### Using as Library

```python
import asyncio
from sgr_agent_core import AgentDefinition, AgentFactory
from sgr_agent_core.agents import SGRToolCallingAgent
import sgr_agent_core.tools as tools

async def main():
    agent_def = AgentDefinition(
        name="my_agent",
        base_class=SGRToolCallingAgent,
        tools=[tools.GeneratePlanTool, tools.FinalAnswerTool],
        llm={
            "api_key": "your-api-key",
            "base_url": "https://api.openai.com/v1",
        },
    )

    agent = await AgentFactory.create(
        agent_def=agent_def,
        task_messages=[{"role": "user", "content": "Research AI trends"}],
    )

    result = await agent.execute()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation

- **[Installation](installation.md)** — Detailed installation instructions for pip and Docker
- **[Agent Core Framework](../framework/main-concepts.md)** — Understand the core concepts and architecture
- **[Using as Library](../framework/first-steps.md)** — Learn how to use SGR Agent Core as a Python library
- **[API Server Quick Start](../sgr-api/SGR-Quick-Start.md)** — Get started with the REST API service

## Contact & Community

**For collaboration inquiries**: [@VaKovaLskii](https://t.me/neuraldeep)

**Community Chat**: We answer questions in [Telegram chat](https://t.me/sgragentcore) (ru/en)

![](../../assets/images/rmr750x200.png)

This project is supported by the AI R&D team at red_mad_robot, providing research capacity, engineering expertise, infrastructure, and operational support.

Learn more about red_mad_robot: [redmadrobot.ai](https://redmadrobot.ai/)↗️ [habr](https://habr.com/ru/companies/redmadrobot/articles/)↗️ [telegram](https://t.me/Redmadnews/)↗️
