Эта таблица сравнивает доступные типы агентов в SGR Agent Core, показывая их подходы к реализации, возможности рассуждений, доступные инструменты, паттерны API запросов и механизмы выбора инструментов.

| Агент                  | Название в API         | Реализация SGR | ReasoningTool        | Инструменты                 | API запросы | Механизм выбора  |
| ---------------------- | ---------------------- | -------------- | -------------------- | --------------------------- | ----------- | ----------------- |
| [SGRAgent](https://github.com/vamplabai/sgr-agent-core/blob/main/sgr_agent_core/agents/sgr_agent.py) | `sgr_agent` | Structured Output  | ❌ Встроен в схему | 6 базовых               | 1            | SO Union Type        |
| [ToolCallingAgent](https://github.com/vamplabai/sgr-agent-core/blob/main/sgr_agent_core/agents/tool_calling_agent.py) | `tool_calling_agent` | ❌ Отсутствует          | ❌ Отсутствует            | 6 базовых               | 1            | FC "required"        |
| [SGRToolCallingAgent](https://github.com/vamplabai/sgr-agent-core/blob/main/sgr_agent_core/agents/sgr_tool_calling_agent.py) | `sgr_tool_calling_agent` | FC Tool принудительно   | ✅ Первый шаг FC     | 7 (6 + ReasoningTool) | 2            | FC → FC    ЛУЧШИЙ АГЕНТ |
