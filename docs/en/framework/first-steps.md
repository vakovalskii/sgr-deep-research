# Quick Start

This guide will help you quickly get started with SGR Agent Core as a Python library.

### Installation

Install the library via pip:

```bash
pip install sgr-agent-core
```

### **Example 1: Creating an Agent Directly**

The conventional way to create an agent is through the class constructor.</br>
In this case, full control over which components, adapters, and tools will be used at startup remains with the user.

```py
import asyncio
import logging
from openai import AsyncOpenAI

import sgr_agent_core.tools as tools
from sgr_agent_core import AgentConfig
from sgr_agent_core.agents import SGRToolCallingAgent  # (1)!

logging.basicConfig(level=logging.INFO)

async def main():
    agent_config = AgentConfig()  # (2)!
    agent_config.llm.api_key = "___"  # Or just set in ENV
    agent_config.llm.base_url = "___"  # Or just set in ENV
    openai_client = AsyncOpenAI(api_key=agent_config.llm.api_key,
                                base_url=agent_config.llm.base_url)

    toolkit = [  # (3)!
        tools.GeneratePlanTool,
        tools.FinalAnswerTool,
    ]

    # Create agent directly
    agent = SGRToolCallingAgent(
        task="Write a forecast of the main trends in the development of artificial intelligence",
        openai_client=openai_client,
        agent_config=agent_config,
        toolkit=toolkit,
    )

    print(await agent.execute())


if __name__ == "__main__":
    asyncio.run(main())
```

1. This agent uses exclusively native tool calling, making it well-suited for getting started
2. Default parameters will be set here if you don't override some of them
3. For the example, we'll take a minimal pair of tools that will allow getting an answer to the task and completing the agent's work.
   Learn more about tools in the [tools documentation](tools.md)

???example "Example of Agent Reasoning Log"
    ```log
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:🚀 Starting for task: 'Write a forecast of the main trends in the development of artificial intelligence'
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:Step 1 started
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:
        ###############################################
        🤖 LLM RESPONSE DEBUG:
           🧠 Reasoning Steps: ['Identify the key trends in artificial intelligence development up to 2025.', 'Analyze the potential future directions based on current advancements and research.', 'Compile a comprehensive forecast based on the identified trends.']
           📊 Current Situation: 'Research on artificial intelligence trends has been conducted, focusing on advancements, challenges, and future directions. Key areas include machine learning, natural language processing, and ethical considerations....'
           📋 Plan Status: 'Research plan is in progress, focusing on compiling trends and forecasts....'
           🔍 Searches Done: 0
           🔍 Clarifications Done: 0
           ✅ Enough Data: False
           📝 Remaining Steps: ['Gather data on recent AI advancements and trends from 2023 to 2025.', 'Analyze the implications of these trends for future AI development.', 'Draft the forecast report based on the findings.']
           🏁 Task Completed: False
           ➡️ Next Step: Gather data on recent AI advancements and trends from 2023 to 2025.
        ###############################################
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:
    ###############################################
    🛠️ TOOL EXECUTION DEBUG:
        🔧 Tool Name: generateplantool
        📋 Tool Model: {
      "reasoning": "To provide a comprehensive forecast on the development of artificial intelligence, it is essential to gather data on recent advancements and analyze the implications of these trends. This will help in identifying key areas of growth and potential challenges in the field.",
      "research_goal": "Forecast the main trends in the development of artificial intelligence up to 2025 and beyond.",
      "planned_steps": [
        "Gather data on AI advancements from 2023 to 2025, focusing on machine learning, natural language processing, and ethical considerations.",
        "Analyze the implications of these trends for future AI development, including potential applications and societal impact.",
        "Draft a comprehensive forecast report based on the findings."
      ],
      "search_strategies": [
        "Conduct literature review on AI trends from 2023 to 2025.",
        "Analyze industry reports and expert opinions on the future of AI."
      ]
    }
        🔍 Result: '{
      "research_goal": "Forecast the main trends in the development of artificial intelligence up to 2025 and beyond.",
      "planned_steps": [
        "Gather data on AI advancements from 2023 to 2025, focusing on machine learning, natural language processing, and ethical considerations.",
        "Analyze the implications of these trends for future AI development, including potential applications and societa...'
    ###############################################
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:Step 2 started
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:
        ###############################################
        🤖 LLM RESPONSE DEBUG:
           🧠 Reasoning Steps: ['Conduct literature review on AI trends from 2023 to 2025.', 'Analyze industry reports and expert opinions on the future of AI.', 'Compile findings into a comprehensive forecast report.']
           📊 Current Situation: 'The research plan is established to gather data on AI advancements and trends from 2023 to 2025....'
           📋 Plan Status: 'Research plan is ready for execution, focusing on literature and industry analysis....'
           🔍 Searches Done: 0
           🔍 Clarifications Done: 0
           ✅ Enough Data: False
           📝 Remaining Steps: ['Conduct literature review on AI trends from 2023 to 2025.', 'Analyze industry reports and expert opinions on the future of AI.', 'Draft the forecast report based on the findings.']
           🏁 Task Completed: False
           ➡️ Next Step: Conduct literature review on AI trends from 2023 to 2025.
        ###############################################
    INFO:sgr_agent_core.agents.sgr_tool_calling_agent_923e6191-b3a9-4ef1-b4af-c1a2c587e512:
    ###############################################
    🛠️ TOOL EXECUTION DEBUG:
        🔧 Tool Name: finalanswertool
        📋 Tool Model: {
      "reasoning": "The research plan has been established to gather data on AI advancements and trends from 2023 to 2025. A literature review and analysis of industry reports will provide insights into future developments.",
      "completed_steps": [
        "Research plan established to gather data on AI advancements and trends.",
        "Planned literature review and analysis of industry reports on AI."
      ],
      "answer": "The forecast of main trends in the development of artificial intelligence includes advancements in machine learning algorithms, increased focus on ethical AI, and the integration of AI in various sectors such as healthcare, finance, and education. Additionally, natural language processing will continue to evolve, making AI more accessible and user-friendly. The societal impact of AI, including job displacement and privacy concerns, will also shape future regulations and development.",
      "status": "completed"
    }
        🔍 Result: '{
      "reasoning": "The research plan has been established to gather data on AI advancements and trends from 2023 to 2025. A literature review and analysis of industry reports will provide insights into future developments.",
      "completed_steps": [
        "Research plan established to gather data on AI advancements and trends.",
        "Planned literature review and analysis of industry reports on AI."
      ...'
    ###############################################
    ```
    It's hard not to acknowledge that the agent's default behavior is set for more complex tasks than trivial question-answer

!!! Tip "Learn More About `AgentConfig`"
    For a more detailed overview of all available agent configuration parameters,
    check the [`config.yaml.example`](https://github.com/vamplabAI/sgr-deep-research/blob/main/config.yaml.example) file.

### **Example 2: Creating an Agent Using Definition and Factory**

For more flexible configuration management and reusing settings, you can use `AgentDefinition` and `AgentFactory`. In this case, some assembly tasks, such as creating MCP tools or organizing the LLM client, will be handled inside the factory.

```py
import asyncio
import logging

import sgr_agent_core.tools as tools
from sgr_agent_core import AgentDefinition
from sgr_agent_core import AgentFactory
from sgr_agent_core.agents import SGRToolCallingAgent

logging.basicConfig(level=logging.INFO)

async def main():
    # Define agent through AgentDefinition
    agent_def = AgentDefinition(
        name="my_research_agent",  # (1)!
        base_class=SGRToolCallingAgent,  # (2)!
        tools=[
            tools.GeneratePlanTool,
            tools.FinalAnswerTool,
        ],
        llm={
            "api_key": "___",  # Or just set in ENV
            "base_url": "___",  # Or just set in ENV
        },
    )

    # Create agent through Factory
    agent = await AgentFactory.create(
        agent_def=agent_def,
        task="Write a forecast of the main trends in the development of artificial intelligence",
    )

    print(await agent.execute())


if __name__ == "__main__":
    asyncio.run(main())
```

1. Set a custom name for this agent configuration. It's used in logs, registries, API, etc.

2. Specify the base class - which agent logic implementation the configuration will be applied to. You can use any of:

   - Implemented in the framework
   - Imported into the project code and added to Registry
   - Specified as a module via [Pydantic ImportString](https://docs.pydantic.dev/latest/api/types/#pydantic.types.ImportString)

### **Example 3: Creating from Configuration Files**

You can use YAML configuration files `config.yaml` and `agents.yaml` to define agents.
This approach helps reduce code and simplify configuration management for different environments and tasks

**config.yaml:**

```yaml
llm:
  base_url: "___"
  api_key: "___"
  model: "gpt-4o"
  max_tokens: 2000
  temperature: 0.2
execution:
  max_clarifications: 3
  max_iterations: 7
```

**agents.yaml**

```yaml
agents:
  simple_search_agent:
    base_class: "ResearchSGRToolCallingAgent"
    llm:
      model: "gpt-4.1-mini"
    tools:
      - "WebSearchTool"
      - "FinalAnswerTool"
    search:
      tavily_api_key: "___"
      max_results: 5
      content_limit: 5000

  writer_agent:
    base_class: "SGRToolCallingAgent"
    llm:
      temperature: 0.8
    tools:
      - "FinalAnswerTool"
    prompts:
      system_prompt_str: "You are a renowned writer. Write a brief essay on the given topic."
```

!!! tip
    The contents of agents.yaml can be placed directly in config.yaml to have a single configuration file,
    it will be applied by the `GlobalConfig.from_yaml("config.yaml")` command

```python
import asyncio
import logging

from sgr_agent_core import AgentFactory, GlobalConfig

logging.basicConfig(level=logging.INFO)


async def main():
    config = GlobalConfig.from_yaml("config.yaml")
    config.definitions_from_yaml("agents.yaml")

    agent1 = await AgentFactory.create(
        agent_def=config.agents["simple_search_agent"],
        task="Research the impact of climate change on the economy",
    )
    agent2 = await AgentFactory.create(
        agent_def=config.agents["writer_agent"],
        task='What is the existential question of the lyrical hero in Shakespeare\'s "Hamlet"?',
    )

    print(agent1.config.model_dump_json(indent=2))
    print(agent2.config.model_dump_json(indent=2))
    print(await agent1.execute())
    print(await agent2.execute())


if __name__ == "__main__":
    asyncio.run(main())
```

??? example "Configuration of simple_search_agent"
    ```json
    {
      "llm": {
        "api_key": "***",
        "base_url": "***",
        "model": "gpt-4.1-mini",
        "max_tokens": 2000,
        "temperature": 0.2,
        "proxy": null
      },
      "search": {
        "tavily_api_key": "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",
        "tavily_api_base_url": "https://api.tavily.com",
        "max_searches": 4,
        "max_results": 5,
        "content_limit": 5000
      },
      "execution": {
        "max_clarifications": 3,
        "max_iterations": 7,
        "mcp_context_limit": 15000,
        "logs_dir": "logs",
        "reports_dir": "reports"
      },
      "prompts": {
        "system_prompt_file": "sgr_agent_core\\prompts\\system_prompt.txt",
        "initial_user_request_file": "sgr_agent_core\\prompts\\initial_user_request.txt",
        "clarification_response_file": "sgr_agent_core\\prompts\\clarification_response.txt",
        "system_prompt_str": null,
        "initial_user_request_str": null,
        "clarification_response_str": null,
        "system_prompt": "<MAIN_TASK_GUIDELINES>\nYou are an expert researcher with adaptive planning and schema-guided-reasoning capabilities. You get the research task and you neeed to do research and genrete answer\n</MAIN_TASK_GUIDELINES>\n\n<DATE_GUIDELINES>\nPAY ATTENTION TO THE DATE INSIDE THE USER REQUEST\nDATE FORMAT: YYYY-MM-DD HH:MM:SS (ISO 8601)...",
        "initial_user_request": "Current Date: {current_date} (Year-Month-Day ISO format: YYYY-MM-DD HH:MM:SS)\nORIGINAL USER REQUEST:\n\n{task}\n",
        "clarification_response": "Current Date: {current_date} (Year-Month-Day ISO format: YYYY-MM-DD HH:MM:SS)\n\nCLARIFICATIONS:\n\n{clarifications}\n"
      },
      "mcp": {
        "mcpServers": {}
      },
      "name": "simple_search_agent",
      "base_class": "ResearchSGRToolCallingAgent",
      "tools": [
        "WebSearchTool",
        "FinalAnswerTool"
      ]
    }
    ```

??? example "Configuration of writer_agent"
    ```json
    {
      "llm": {
        "api_key": "***",
        "base_url": "***",
        "model": "gpt-4o",
        "max_tokens": 2000,
        "temperature": 0.8,
        "proxy": null
      },
      "search": null,
      "execution": {
        "max_clarifications": 3,
        "max_iterations": 7,
        "mcp_context_limit": 15000,
        "logs_dir": "logs",
        "reports_dir": "reports"
      },
      "prompts": {
        "system_prompt_file": "sgr_agent_core\\prompts\\system_prompt.txt",
        "initial_user_request_file": "sgr_agent_core\\prompts\\initial_user_request.txt",
        "clarification_response_file": "sgr_agent_core\\prompts\\clarification_response.txt",
        "system_prompt_str": "You are a renowned writer. Write a brief essay on the given topic.",
        "initial_user_request_str": null,
        "clarification_response_str": null,
        "system_prompt": "You are a renowned writer. Write a brief essay on the given topic.",
        "initial_user_request": "Current Date: {current_date} (Year-Month-Day ISO format: YYYY-MM-DD HH:MM:SS)\nORIGINAL USER REQUEST:\n\n{task}\n",
        "clarification_response": "Current Date: {current_date} (Year-Month-Day ISO format: YYYY-MM-DD HH:MM:SS)\n\nCLARIFICATIONS:\n\n{clarifications}\n"
      },
      "mcp": {
        "mcpServers": {}
      },
      "name": "writer_agent",
      "base_class": "SGRToolCallingAgent",
      "tools": [
        "FinalAnswerTool"
      ]
    }
    ```

!!!warning
    When connecting your own agents or tools, make sure the file is imported/located within the project.
    Otherwise, it won't be added to the Registry and you'll get an error: <br>
    `ValueError: Agent base class 'YourOwnAgent' not found in registry.`

## Next Steps

TBC
