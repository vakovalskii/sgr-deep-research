# Собери своего агента

В этом разделе погрузимся в техническую реализацию агента и разберём подробнее, как это можно адаптировать под свои нужды

!!! Tip "Архитектура агентов"
    Информация о доступных агентах и их различиях находится в [Основных концепциях](main-concepts.md#agent).


*Для детального понимания полной логики лучше ознакомиться с [исходным кодом](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_agent.py).*

## Интерфейс

Упрощённое представление основного цикла работы:
```py
while agent.state not in FINISH_STATES:
    reasoning = await agent._reasoning_phase()
    action_tool = await agent._select_action_phase(reasoning)
    await agent._action_phase(action_tool)
```


В `BaseAgent` предоставлен минимальный интерфейс для модификации поведения агента и работы с контекстом.

### Основные атрибуты агента

```py
class BaseAgent:
    # Идентификация
    id: str                                    # Уникальный идентификатор агента
    name: str                                  # Имя класса агента
    task: str                                  # Задача для выполнения

    # Конфигурация и клиенты
    config: AgentConfig                        # Конфигурация агента
    openai_client: AsyncOpenAI                 # Клиент для работы с LLM API

    # Контекст и состояние
    _context: AgentContext                    # Контекст выполнения агента
    conversation: list[dict]                  # История диалога с LLM

    # Инструменты и стриминг
    toolkit: list[Type[BaseTool]]             # Набор доступных инструментов
    streaming_generator: OpenAIStreamingGenerator  # Генератор стриминга
```

### Методы для переопределения

При создании собственных решений стоит обратить внимание в первую очередь на эти методы:
```py

    async def _prepare_context(self) -> list[dict]:
        """Prepare a conversation context with system prompt, task data and any
        other context. Override this method to change the context setup for the
        agent.

        Returns a list of dictionaries OpenAI like format, each containing a role and
        content key by default.
        """
        return [
            {"role": "system", "content": PromptLoader.get_system_prompt(self.toolkit, self.config.prompts)},
            {
                "role": "user",
                "content": PromptLoader.get_initial_user_request(self.task, self.config.prompts),
            },
            *self.conversation,
        ]

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for the current agent state and progress.
        Override this method to change the tool setup or conditions for tool
        usage.

        Returns a list of ChatCompletionFunctionToolParam based
        available tools.
        """
        tools = set(self.toolkit)
        if self._context.iteration >= self.config.execution.max_iterations:
            raise RuntimeError("Max iterations reached")
        return [pydantic_function_tool(tool, name=tool.tool_name) for tool in tools]

    async def _reasoning_phase(self) -> ReasoningTool:
        """Call LLM to decide next action based on current context."""
        raise NotImplementedError("_reasoning_phase must be implemented by subclass")

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
        """Select the most suitable tool for the action decided in the
        reasoning phase.

        Returns the tool suitable for the action.
        """
        raise NotImplementedError("_select_action_phase must be implemented by subclass")

    async def _action_phase(self, tool: BaseTool) -> str:
        """Call Tool for the action decided in the select_action phase.

        Returns string or dumped JSON result of the tool execution.
        """
        raise NotImplementedError("_action_phase must be implemented by subclass")

    async def _execution_step(self):
        """Execute a single step of the agent workflow.

        Note: Override this method to change the agent workflow for each step.
        """
        raise NotImplementedError("_execution_step must be implemented by subclass")
```
## Основные модули агента


### AgentConfig

Хранит все настройки агента: параметры LLM, поиска, выполнения, промпты и MCP конфигурацию.

!!! Tip "Подробнее о конфигурации"
    Полное описание системы конфигурации, иерархии настроек и примеры использования находятся в [руководстве по конфигурации](configuration.md).

#### Расширение конфигурации

Имеющиеся схемы конфига позволяют расширять поля без изменения базового класса:

**Пример 1: Добавление полей в YAML**

```yaml
agents:
  custom_agent:
    base_class: "SGRAgent"
    execution:
      max_iterations: 15
      # Кастомные поля
      custom_timeout: 300
      retry_count: 5
      enable_caching: true
    tools:
      - "WebSearchTool"
      - "FinalAnswerTool"
```

**Пример 2: Использование кастомных полей в AgentDefinition**

```python
from sgr_agent_core import AgentDefinition
from sgr_agent_core.agent_definition import ExecutionConfig
from sgr_agent_core.agents import SGRAgent

# Кастомные поля можно добавить напрямую в ExecutionConfig
agent_def = AgentDefinition(
    name="custom_agent",
    base_class=SGRAgent,
    execution=ExecutionConfig(
        max_iterations=15,
        custom_timeout=600,
        retry_count=5,
        enable_caching=True
),
    tools=["WebSearchTool", "FinalAnswerTool"]
)
```

**Пример 3: Использование кастомных полей в агенте**

```python
class CustomAgent(BaseAgent):
    async def _action_phase(self, tool: BaseTool) -> str:
        # Прямой доступ к кастомным полям
        timeout = self.config.execution.custom_timeout
        retry_count = self.config.execution.retry_count

        if self.config.execution.enable_caching:
            # Логика с кешированием
            pass

        result = await tool(self._context, self.config)
        return result
```

!!! Important "Важно: extra='allow'"
    Благодаря `extra="allow"`  pydantic модели `ExecutionConfig`, все пользовательские атрибуты или дополнительные поля из YAML автоматически сохраняются и доступны через атрибуты объекта.

### LLM адаптер

Клиент для взаимодействия с LLM API. Используется для всех запросов к языковой модели.
В существующих агентах используется `openai-python` клиент.


### Streaming_generator — модуль стриминга

Идея модуля - регистрировать эвенты, происходящие в системе и выдавать результат по мере работы агента.
Обеспечивает потоковую передачу ответов от агента в формате, совместимом с OpenAI API.

Стандартно поставляемая реализация содержит OpenAI-like streaming протокол как некоторое компромиссно-универсальное решение для совместимости. В зависимости от задач вашей системы этот модуль стоит переработать под более удобный/лаконичный формат


Для получения стрима используйте асинхронный итератор. События будут пополняться по мере их добавления в генератор:
```python
async for chunk in agent.streaming_generator:
    print(chunk, end="")
```

### _context — контекст выполнения

Хранит состояние агента, данные, счётчики и результаты выполнения.

```python
# Основные поля:
state                    # Идентификатор текущего состояния агента
iteration                # Номер текущей итерации
clarifications_used      # Количество заданных запросов на уточнения
execution_result         # Финальный результат выполнения агента
custom_context           # Раздел для любых пользовательских данных
```
### toolkit — набор инструментов

Список классов инструментов, доступных агенту для выполнения действий.

```python
self.toolkit: list[Type[BaseTool]]

# Пример набора инструментов:
self.toolkit = [
    WebSearchTool,
    ExtractPageContentTool,
    CreateReportTool,
    FinalAnswerTool
]

# Использование в _prepare_tools():
tools = set(self.toolkit)
# Фильтрация инструментов на основе состояния
if self._context.searches_used >= self.config.search.max_searches:
    tools -= {WebSearchTool}
```

### conversation — история диалога

Список сообщений в формате OpenAI для поддержания контекста разговора с LLM.

```python
conversation: list[dict]

# Формат сообщений:
conversation = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {
        "role": "assistant",
        "content": "...",
        "tool_calls": [{"type": "function", "id": "...", "function": {...}}]
    },
    {"role": "tool", "content": "...", "tool_call_id": "..."}
]
```

## Примеры использования собственных агентов

### Пример 1: Research агент с переопределением _prepare_tools

`ResearchSGRAgent` демонстрирует, как переопределить `_prepare_tools()` для динамического управления инструментами на основе состояния агента:

```python
from typing import Type
from sgr_agent_core.agents import SGRAgent
from sgr_agent_core.tools import (
    ClarificationTool,
    CreateReportTool,
    FinalAnswerTool,
    WebSearchTool,
)
from sgr_agent_core.next_step_tool import NextStepToolsBuilder, NextStepToolStub

class ResearchSGRAgent(SGRAgent):

    async def _prepare_tools(self) -> Type[NextStepToolStub]:
        tools = set(self.toolkit)

        if self._context.iteration >= self.config.execution.max_iterations:  # (1)!
            tools = {
                CreateReportTool,
                FinalAnswerTool,
            }

        if self._context.clarifications_used >= self.config.execution.max_clarifications:  # (2)!
            tools -= {ClarificationTool}

        if self._context.searches_used >= self.config.search.max_searches:  # (3)!
            tools -= {WebSearchTool}

        return NextStepToolsBuilder.build_NextStepTools(list(tools))
```

1. Если достигнут лимит итераций, оставляем только финальные инструменты для завершения работы
2. Если исчерпаны уточнения, убираем `ClarificationTool` из доступных инструментов
3. Если исчерпаны поиски, убираем `WebSearchTool` из доступных инструментов

!!! Tip "Стейтмашина для управления инструментами... Или что-то большее"
    Для более сложной логики управления инструментами можно использовать более серьёзный движок состояний. Это позволит явно определить состояния агента и правила перехода между ними, что упростит управление доступными инструментами на каждом этапе работы.

### Пример 2: Агент для анализа данных

```python
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import BaseTool, FinalAnswerTool
from sgr_agent_core.tools.reasoning_tool import ReasoningTool

class DataAnalysisTool(BaseTool):
    """Инструмент для анализа данных."""
    tool_name: str = "data_analysis"
    description: str = "Analyzes provided data"

    data: str

    async def __call__(self, context, config, **kwargs) -> str:
        # Логика анализа данных
        return f"Analysis result for: {self.data}"

class DataAnalysisAgent(BaseAgent):
    """Агент для анализа данных."""

    name: str = "data_analysis_agent"

    async def _select_action_phase(self, reasoning):
        if "analyze" in reasoning.remaining_steps:
            return DataAnalysisTool(data=self.task)
        return FinalAnswerTool(answer="Analysis complete")

    async def _action_phase(self, tool):
        result = await tool(self._context, self.config)
        if isinstance(tool, FinalAnswerTool):
            self._context.execution_result = result
            self._context.state = AgentStatesEnum.COMPLETED
        return result
```


## Общие рекомендации

!!! Tip "Важные моменты"

    - **Наследуйтесь от готовых агентов**: Используйте `SGRAgent` или `ToolCallingAgent` как базовые классы вместо `BaseAgent`, если вам не нужна полная кастомизация

    - **Регистрация агентов**: Убедитесь, что ваш кастомный агент импортирован в проект  или YAML конфигурацию до использования через `AgentFactory`

    - **Асинхронность**: Все методы работы с LLM и инструментами должны быть асинхронными

    - **Память контекста**: `conversation` накапливается во время выполнения, следите за размером и содержанием для избежания снижения качества LLM генерации
