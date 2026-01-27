This table compares the available agent types in SGR Agent Core, showing their implementation approaches, reasoning capabilities, available tools, API request patterns, and tool selection mechanisms.

| Agent                  | API Name              | SGR Implementation | ReasoningTool        | Tools                 | API Requests | Selection Mechanism  |
| ---------------------- | --------------------- | ------------------ | -------------------- | --------------------- | ------------ | -------------------- |
| [SGRAgent](https://github.com/vamplabai/sgr-agent-core/blob/main/sgr_agent_core/agents/sgr_agent.py) | `sgr_agent` | Structured Output  | ❌ Built into schema | 6 basic               | 1            | SO Union Type        |
| [ToolCallingAgent](https://github.com/vamplabai/sgr-agent-core/blob/main/sgr_agent_core/agents/tool_calling_agent.py) | `tool_calling_agent` | ❌ Absent          | ❌ Absent            | 6 basic               | 1            | FC "required"        |
| [SGRToolCallingAgent](https://github.com/vamplabai/sgr-agent-core/blob/main/sgr_agent_core/agents/sgr_tool_calling_agent.py) | `sgr_tool_calling_agent` | FC Tool enforced   | ✅ First step FC     | 7 (6 + ReasoningTool) | 2            | FC → FC    TOP AGENT |
