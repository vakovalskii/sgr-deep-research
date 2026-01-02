# SGR Agent Core — the first SGR open-source agentic framework for Schema-Guided Reasoning

## Description

![SGR Concept Architecture](https://github.com/vamplabAI/sgr-agent-core/blob/main/docs/assets/images/sgr_concept.png)
Open-source agentic framework for building intelligent research agents using Schema-Guided Reasoning. The project provides a core library with a extendable BaseAgent interface implementing a two-phase architecture and multiple ready-to-use research agent implementations built on top of it.

The library includes extensible tools for search, reasoning, and clarification, real-time streaming responses, OpenAI-compatible REST API. Works with any OpenAI-compatible LLM, including local models for fully private research.

______________________________________________________________________

## Documentation

> **Get started quickly with our documentation:**

- **[Project Docs](https://vamplabai.github.io/sgr-agent-core/)** - Complete project documentation
- **[Framework Quick Start Guide](https://vamplabai.github.io/sgr-agent-core/framework/first-steps/)** - Get up and running in minutes
- **[DeepSearch Service Documentation](https://vamplabai.github.io/sgr-agent-core/sgr-api/SGR-Quick-Start/)** - REST API reference with examples

______________________________________________________________________

## Quick Start

### Installation

```bash
pip install sgr-agent-core
```

### Running Research Agents

The project includes example research agent configurations in the `examples/` directory. To get started with deep research agents:

1. Copy and configure the config file:

```bash
cp examples/sgr_deep_research/config.yaml my_config.yaml
# Edit my_config.yaml and set your API keys:
# - llm.api_key: Your OpenAI API key
# - search.tavily_api_key: Your Tavily API key (optional)
```

2. Run the API server using the `sgr` utility:

```bash
sgr --config-file examples/sgr_deep_research/config.yaml
```

The server will start on `http://localhost:8010` with OpenAI-compatible API endpoints.

> **Note:** You can also run the server directly with Python:
>
> ```bash
> python -m sgr_agent_core.server --config-file examples/sgr_deep_research/config.yaml
> ```

For more examples and detailed usage instructions, see the [examples/](examples/) directory.

______________________________________________________________________

## Benchmarking

![SimpleQA Benchmark Comparison](https://github.com/vamplabAI/sgr-agent-core/blob/main/docs/assets/images/simpleqa_benchmark_comparison.png)

**Performance Metrics on gpt-4.1-mini:**

- **Accuracy:** 86.08%
- **Correct:** 3,724 answers
- **Incorrect:** 554 answers
- **Not Attempted:** 48 answers

More detailed benchmark results are available [here](https://github.com/vamplabAI/sgr-agent-core/blob/main/benchmark/simpleqa_benchmark_results.md).

______________________________________________________________________

## Open-Source Development Team

*All development is driven by pure enthusiasm and open-source community collaboration. We welcome contributors of all skill levels!*

- **SGR Concept Creator** // [@abdullin](https://t.me/llm_under_hood)
- **Project Coordinator & Vision** // [@VaKovaLskii](https://t.me/neuraldeep)
- **Lead Core Developer** // [@virrius](https://t.me/virrius_tech)
- **API Development** // [@EvilFreelancer](https://t.me/evilfreelancer)
- **DevOps & Deployment** // [@mixaill76](https://t.me/mixaill76)

If you have any questions - feel free to join our [community chat](https://t.me/sgragentcore)↗️ or reach out [Valerii Kovalskii](https://www.linkedin.com/in/vakovalskii/)↗️.

## Special Thanks To:

This project is developed by the **neuraldeep** community. It is inspired by the Schema-Guided Reasoning (SGR) work and [SGR Agent Demo](https://abdullin.com/schema-guided-reasoning/demo)↗️ delivered by "LLM Under the Hood" community and AI R&D Hub of [TIMETOACT GROUP Österreich](https://www.timetoact-group.at)↗️

![](./docs/assets/images/rmr750x200.png)

This project is supported by the AI R&D team at red_mad_robot, providing research capacity, engineering expertise, infrastructure, and operational support.

Learn more about red_mad_robot: [redmadrobot.ai](https://redmadrobot.ai/)↗️ [habr](https://habr.com/ru/companies/redmadrobot/articles/)↗️ [telegram](https://t.me/Redmadnews/)↗️

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=vamplabAI/sgr-agent-core&type=Date)](https://star-history.com/#vamplabAI/sgr-agent-core&Date)
