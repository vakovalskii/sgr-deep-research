# QnA

## How to best learn the framework?

**Question:** Is it normal that it's difficult to understand the entire repository? What's the most important thing to study to understand how everything works from the inside?

**Answer:** This is absolutely normal — the repository really has a lot of code and abstractions, especially when it comes to library code. Recommended study order:

**1. Basics**

- **`sgr_agent_core`** — the framework core, not very much code, but quite complex things. Understanding it — and everything else will become clear
- **`base_agent`**, **`base_tool`** — fairly simple and understandable classes

**2. Models and organization**

- **`models`** — you'll get a picture of how the agent, context, and work with web sources are organized

**3. Specific implementations**

- **`agents/`** and **`tools/`** — specific implementations of agents and tools

**4. Wrapper and infrastructure**

- **`AgentDefinition` and `AgentConfig`** — the [documentation](configuration.md) already explains why it's so complex
- **`services/registry` + `agent_factory`** — the final picture of how everything works will come together

**5. Remaining topics**

- **`mcp`** and **`stream`** — for the finale

After that, you can study **`sgr_deep_research`** — it's literally an API wrapper for the framework agents.

**Result:** Congratulations, you're at least at the contributor level
