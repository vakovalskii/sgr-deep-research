# SGR Agent Core — the first SGR open-source agentic framework for Schema-Guided Reasoning

![SGR Concept Architecture](https://github.com/vamplabAI/sgr-agent-core/blob/main/docs/assets/images/sgr_concept.png)

Open-source agentic framework for building intelligent research agents using Schema-Guided Reasoning. The project provides a core library with a extendable BaseAgent interface implementing a two-phase architecture and multiple ready-to-use research agent implementations built on top of it.

The library includes extensible tools for search, reasoning, and clarification, real-time streaming responses, OpenAI-compatible REST API. Works with any OpenAI-compatible LLM, including local models for fully private research.

## Why use SGR Agent Core?

- **Schema-Guided Reasoning** — SGR combines structured reasoning with flexible tool selection
- **Multiple Agent Types** — Choose from `SGRAgent`, `ToolCallingAgent`, or `SGRToolCallingAgent`
- **Extensible Architecture** — Easy to create custom agents and tools
- **OpenAI-Compatible API** — Drop-in replacement for OpenAI API endpoints
- **Real-time Streaming** — Built-in support for streaming responses via SSE
- **Production Ready** — Battle-tested with comprehensive test coverage and Docker support

## Documentation

> **Get started quickly with our documentation:**

- **[Project Docs](https://vamplabai.github.io/sgr-agent-core/)** - Complete project documentation
- **[Framework Quick Start Guide](https://vamplabai.github.io/sgr-agent-core/framework/first-steps/)** - Get up and running in minutes
- **[DeepSearch Service Documentation](https://vamplabai.github.io/sgr-agent-core/sgr-api/SGR-Quick-Start/)** - REST API reference with examples

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
# Edit examples/sgr_deep_research/config.yaml and set your API keys:
# - llm.api_key: Your OpenAI API key
# - search.tavily_api_key: Your Tavily API key (optional)

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

The API server will be available at `http://localhost:8010` with OpenAI-compatible API endpoints. Interactive API documentation (Swagger UI) is available at `http://localhost:8010/docs`.

### Installation

If you want to use SGR Agent Core as a Python library (framework):

```bash
pip install sgr-agent-core
```

See the [Installation Guide](https://vamplabai.github.io/sgr-agent-core/getting-started/installation/) for detailed instructions and the [Using as Library](https://vamplabai.github.io/sgr-agent-core/framework/first-steps/) guide to get started.

### Running Research Agents

The project includes example research agent configurations in the `examples/` directory. To get started with deep research agents:

1. Copy and configure the config file:

```bash
cp examples/sgr_deep_research/config.yaml.example examples/sgr_deep_research/config.yaml
# Edit examples/sgr_deep_research/config.yaml and set your API keys:
# - llm.api_key: Your OpenAI API key
# - search.tavily_api_key: Your Tavily API key (optional)
```

2. Run the API server using the `sgr` utility:

```bash
sgr --config-file examples/sgr_deep_research/config.yaml
# or use short option
sgr -c examples/sgr_deep_research/config.yaml
```

> **Note:** You can also run the server directly with Python:
>
> ```bash
> python -m sgr_agent_core.server --config-file examples/sgr_deep_research/config.yaml
> ```

### Using the CLI Tool (`sgrsh`)

For interactive command-line usage, you can use the `sgrsh` utility:

```bash
# Single query mode
sgrsh "Найди цену биткоина"

# With agent selection (e.g. sgr_agent, dialog_agent)
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
- Handles clarification and dialog (intermediate results) requests from agents
- Works with any agent defined in your configuration (e.g. `sgr_agent`, `dialog_agent`)

For more examples and detailed usage instructions, see the [examples/](examples/) directory.

## Benchmarking

![SimpleQA Benchmark Comparison](https://github.com/vamplabAI/sgr-agent-core/blob/main/docs/assets/images/simpleqa_benchmark_comparison.png)

**Performance Metrics on gpt-4.1-mini:**

- **Accuracy:** 86.08%
- **Correct:** 3,724 answers
- **Incorrect:** 554 answers
- **Not Attempted:** 48 answers

More detailed benchmark results are available [here](https://github.com/vamplabAI/sgr-agent-core/blob/main/benchmark/simpleqa_benchmark_results.md).

## Open-Source Development Team

*All development is driven by pure enthusiasm and open-source community collaboration. We welcome contributors of all skill levels!*

- **SGR Concept Creator** // [@abdullin](https://t.me/llm_under_hood)
- **Project Coordinator & Vision** // [@VaKovaLskii](https://t.me/neuraldeep)
- **Lead Core Developer** // [@virrius](https://t.me/virrius_tech)
- **API Development** // [@EvilFreelancer](https://t.me/evilfreelancer)
- **DevOps & Deployment** // [@mixaill76](https://t.me/mixaill76)
- **Hybrid FC research** // [@Shadekss](https://t.me/Shadekss)

If you have any questions - feel free to join our [community chat](https://t.me/sgragentcore)↗️ or reach out [Valerii Kovalskii](https://www.linkedin.com/in/vakovalskii/)↗️.

## Special Thanks To:

This project is developed by the **neuraldeep** community. It is inspired by the Schema-Guided Reasoning (SGR) work and [SGR Agent Demo](https://abdullin.com/schema-guided-reasoning/demo)↗️ delivered by "LLM Under the Hood" community and AI R&D Hub of [TIMETOACT GROUP Österreich](https://www.timetoact-group.at)↗️

![](./docs/assets/images/rmr750x200.png)

This project is supported by the AI R&D team at red_mad_robot, providing research capacity, engineering expertise, infrastructure, and operational support.

Learn more about red_mad_robot: [redmadrobot.ai](https://redmadrobot.ai/)↗️ [habr](https://habr.com/ru/companies/redmadrobot/articles/)↗️ [telegram](https://t.me/Redmadnews/)↗️

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=vamplabAI/sgr-agent-core&type=Date)](https://star-history.com/#vamplabAI/sgr-agent-core&Date)
