# Документация по тулам

Этот документ описывает все доступные тулы во фреймворке SGR Deep Research, их параметры, поведение и опции конфигурации.

## Категории тулов

Тулы делятся на две категории:

**Системные тулы** — основные тулы, необходимые для функционирования глубокого исследования. Без них исследовательский агент не сможет работать корректно:

- ReasoningTool
- FinalAnswerTool
- CreateReportTool
- ClarificationTool
- GeneratePlanTool
- AdaptPlanTool

**Вспомогательные тулы** — опциональные тулы, расширяющие возможности агента, но не являющиеся строго обязательными:

- WebSearchTool
- ExtractPageContentTool

## BaseTool

Все тулы наследуются от `BaseTool`, который обеспечивает основу функциональности тулов.

**Исходный код:** [sgr_agent_core/base_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_tool.py)

### Класс BaseTool

```python
class BaseTool(BaseModel, ToolRegistryMixin):
    tool_name: ClassVar[str] = None
    description: ClassVar[str] = None

    async def __call__(
        self, context: AgentContext, config: AgentConfig, **kwargs
    ) -> str:
        raise NotImplementedError("Execute method must be implemented by subclass")
```

### Ключевые особенности

- **Автоматическая регистрация**: Тулы автоматически регистрируются в `ToolRegistry` при определении
- **Pydantic-модель**: Все тулы являются Pydantic-моделями, что обеспечивает валидацию и сериализацию
- **Асинхронное выполнение**: Тулы выполняются асинхронно через метод `__call__`
- **Доступ к контексту**: Тулы получают `ResearchContext` и `AgentConfig` для доступа к состоянию и конфигурации

### Создание пользовательских тулов

Для создания пользовательского тула:

1. Наследуйтесь от `BaseTool`
2. Определите параметры тула как Pydantic-поля
3. Реализуйте метод `__call__`
4. Опционально установите переменные класса `tool_name` и `description`

Пример:

```python
from sgr_agent_core.base_tool import BaseTool
from pydantic import Field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext


class CustomTool(BaseTool):
    """Описание того, что делает этот инструмент."""

    tool_name = "customtool"  # Опционально, автогенерируется из имени класса если не задано

    reasoning: str = Field(description="Почему нужен этот тул")
    parameter: str = Field(description="Параметр тула")

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        # Реализация тула
        result = f"Обработано: {self.parameter}"
        return result
```

Тул будет автоматически зарегистрирован и доступен для использования в конфигурациях агентов.

## Системные тулы

### ReasoningTool

**Тип:** Системный тул
**Исходный код:** [sgr_agent_core/tools/reasoning_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/reasoning_tool.py)

Основной тул для агентов со схема-направляемым рассуждением. Определяет следующий шаг рассуждения с возможностями адаптивного планирования.

**Параметры:**

- `reasoning_steps` (list\[str\], 2-3 элемента): Пошаговый процесс рассуждения
- `current_situation` (str, макс. 300 символов): Оценка текущей исследовательской ситуации
- `plan_status` (str, макс. 150 символов): Статус текущего плана
- `enough_data` (bool, по умолчанию=False): Собрано ли достаточно данных
- `remaining_steps` (list\[str\], 1-3 элемента): Оставшиеся шаги действий
- `task_completed` (bool): Завершена ли исследовательская задача

**Поведение:**
Возвращает JSON-представление состояния рассуждения. Используется SGR-агентами для структурирования процесса принятия решений.

**Использование:**
Обязательный тул для SGR-агентов. Должен использоваться перед выполнением любого другого тула в фазе рассуждения.

**Конфигурация:**
Специальная конфигурация не требуется. Поведение тула контролируется промптами агента и настройками LLM.

### FinalAnswerTool

**Тип:** Системный тул
**Исходный код:** [sgr_agent_core/tools/final_answer_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/final_answer_tool.py)

Финализирует исследовательскую задачу и завершает выполнение агента.

**Параметры:**

- `reasoning` (str): Почему задача завершена и как был верифицирован ответ
- `completed_steps` (list\[str\], 1-5 элементов): Сводка выполненных шагов, включая верификацию
- `answer` (str): Исчерпывающий финальный ответ с точными фактическими данными
- `status` (Literal\["completed", "failed"\]): Статус завершения задачи

**Поведение:**

- Устанавливает `context.state` в указанный статус
- Сохраняет `answer` в `context.execution_result`
- Возвращает JSON-представление финального ответа

**Использование:**
Вызывается после завершения исследовательской задачи для финализации выполнения.

**Конфигурация:**
Специальная конфигурация не требуется.

**Пример:**

```yaml
execution:
  max_iterations: 10  # После этого лимита доступны только FinalAnswerTool и CreateReportTool
```

### CreateReportTool

**Тип:** Системный тул
**Исходный код:** [sgr_agent_core/tools/create_report_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/create_report_tool.py)

Создаёт детальный отчёт с цитатами как финальный шаг исследования.

**Параметры:**

- `reasoning` (str): Почему готов создать отчёт сейчас
- `title` (str): Заголовок отчёта
- `user_request_language_reference` (str): Копия оригинального запроса пользователя для языковой согласованности
- `content` (str): Исчерпывающий исследовательский отчёт со встроенными цитатами \[1\], \[2\], \[3\]
- `confidence` (Literal\["high", "medium", "low"\]): Уровень уверенности в результатах

**Поведение:**

- Сохраняет отчёт в файл в `config.execution.reports_dir`
- Формат имени файла: `{timestamp}_{safe_title}.md`
- Включает полное содержимое с разделом источников
- Возвращает JSON с метаданными отчёта (title, content, confidence, sources_count, word_count, filepath, timestamp)

**Использование:**
Финальный шаг после сбора достаточных исследовательских данных.

**Конфигурация:**

```yaml
execution:
  reports_dir: "reports"  # Директория для сохранения отчётов
```

**Важно:**

- Каждое фактическое утверждение в содержимом ДОЛЖНО иметь встроенные цитаты \[1\], \[2\], \[3\]
- Цитаты должны быть интегрированы непосредственно в предложения
- Содержимое должно использовать тот же язык, что и `user_request_language_reference`

### ClarificationTool

**Тип:** Системный тул
**Исходный код:** [sgr_agent_core/tools/clarification_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/clarification_tool.py)

Задаёт уточняющие вопросы при неоднозначном запросе.

**Параметры:**

- `reasoning` (str, макс. 200 символов): Почему нужно уточнение (1-2 предложения МАКСИМУМ)
- `unclear_terms` (list\[str\], 1-3 элемента): Список неясных терминов (кратко, 1-3 слова каждый)
- `assumptions` (list\[str\], 2-3 элемента): Возможные интерпретации (кратко, 1 предложение каждое)
- `questions` (list\[str\], 1-3 элемента): Конкретные уточняющие вопросы (короткие и прямые)

**Поведение:**

- Возвращает вопросы как строку, разделённую переносами строк
- Приостанавливает выполнение агента до получения уточнения
- Устанавливает состояние агента в `WAITING_FOR_CLARIFICATION`
- Увеличивает `context.clarifications_used`

**Использование:**
Используется, когда запрос пользователя неоднозначен или требует дополнительной информации.

**Конфигурация:**

```yaml
execution:
  max_clarifications: 3  # Максимальное количество запросов уточнения у пользователя
```

После достижения `max_clarifications` тул автоматически удаляется из доступных тулов.

### GeneratePlanTool

**Тип:** Системный тул
**Исходный код:** [sgr_agent_core/tools/generate_plan_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/generate_plan_tool.py)

Генерирует исследовательский план для разбиения сложных запросов на управляемые шаги.

**Параметры:**

- `reasoning` (str): Обоснование исследовательского подхода
- `research_goal` (str): Основная исследовательская цель
- `planned_steps` (list\[str\], 3-4 элемента): Список запланированных шагов
- `search_strategies` (list\[str\], 2-3 элемента): Стратегии поиска информации

**Поведение:**

- Возвращает JSON-представление плана (исключая поле reasoning)
- Используется для структурирования сложных исследовательских задач

**Использование:**
Используется в начале исследования для разбиения сложных запросов.

**Конфигурация:**
Специальная конфигурация не требуется.

### AdaptPlanTool

**Тип:** Системный тул
**Исходный код:** [sgr_agent_core/tools/adapt_plan_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/adapt_plan_tool.py)

Адаптирует исследовательский план на основе новых находок.

**Параметры:**

- `reasoning` (str): Почему план нуждается в адаптации на основе новых данных
- `original_goal` (str): Изначальная исследовательская цель
- `new_goal` (str): Обновлённая исследовательская цель
- `plan_changes` (list\[str\], 1-3 элемента): Конкретные изменения, внесённые в план
- `next_steps` (list\[str\], 2-4 элемента): Обновлённые оставшиеся шаги

**Поведение:**

- Возвращает JSON-представление адаптированного плана (исключая поле reasoning)
- Позволяет динамически корректировать план в процессе исследования

**Использование:**
Используется, когда первоначальный план нуждается в модификации на основе обнаруженной информации.

**Конфигурация:**
Специальная конфигурация не требуется.

## Вспомогательные тулы

### WebSearchTool

**Тип:** Вспомогательный тул
**Исходный код:** [sgr_agent_core/tools/web_search_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/web_search_tool.py)

Выполняет поиск в интернете для получения актуальной информации с использованием Tavily Search API.

**Параметры:**

- `reasoning` (str): Почему нужен этот поиск и что ожидается найти
- `query` (str): Поисковый запрос на том же языке, что и запрос пользователя
- `max_results` (int, по умолчанию=5, диапазон 1-10): Максимальное количество результатов

**Поведение:**

- Выполняет поиск через TavilySearchService
- Добавляет найденные источники в словарь `context.sources`
- Создаёт SearchResult и добавляет в `context.searches`
- Увеличивает `context.searches_used`
- Возвращает форматированную строку с поисковым запросом и результатами (заголовки, ссылки, сниппеты)

**Использование:**
Используется для поиска актуальной информации, проверки фактов, исследования текущих событий, технологических обновлений или любой темы, требующей свежей информации.

**Лучшие практики:**

- Используйте конкретные термины и контекст в запросах
- Для аббревиатур добавляйте контекст: "SGR Schema-Guided Reasoning"
- Используйте кавычки для точных фраз: "Structured Output OpenAI"
- Поисковые запросы на ТОМ ЖЕ ЯЗЫКЕ, что и запрос пользователя
- Для вопросов о датах/числах включайте конкретный год/контекст в запрос
- Сниппеты поиска часто содержат прямые ответы — проверяйте их внимательно

**Конфигурация:**

```yaml
search:
  tavily_api_key: "your-tavily-api-key"  # Обязательно: API-ключ Tavily
  tavily_api_base_url: "https://api.tavily.com"  # URL API Tavily
  max_searches: 4  # Максимальное количество поисковых операций
  max_results: 10  # Максимум результатов в поисковом запросе (переопределяет max_results тула, если меньше)
```

После достижения `max_searches` тул автоматически удаляется из доступных тулов.

**Пример:**

```yaml
agents:
  research_agent:
    search:
      max_searches: 6
      max_results: 15
    tools:
      - "WebSearchTool"
```

### ExtractPageContentTool

**Тип:** Вспомогательный тул
**Исходный код:** [sgr_agent_core/tools/extract_page_content_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/extract_page_content_tool.py)

Извлекает полное детальное содержимое с конкретных веб-страниц с использованием Tavily Extract API.

**Параметры:**

- `reasoning` (str): Почему нужно извлечь эти конкретные страницы
- `urls` (list\[str\], 1-5 элементов): Список URL для извлечения полного содержимого

**Поведение:**

- Извлекает полное содержимое с указанных URL через TavilySearchService
- Обновляет существующие источники в `context.sources` полным содержимым
- Для новых URL добавляет их с последовательной нумерацией
- Возвращает форматированную строку с превью извлечённого содержимого (ограничено `content_limit`)

**Использование:**
Вызывается после WebSearchTool для получения детальной информации с перспективных URL, найденных в результатах поиска.

**Важные предупреждения:**

- Извлечённые страницы могут показывать данные за ДРУГИЕ годы/периоды времени, чем запрошено
- ВСЕГДА проверяйте, что извлечённое содержимое соответствует временному контексту вопроса
- Если извлечённое содержимое противоречит поисковому сниппету, предпочитайте сниппет для фактических вопросов
- Для вопросов о датах/числах перепроверяйте извлечённые значения с поисковыми сниппетами

**Конфигурация:**

```yaml
search:
  tavily_api_key: "your-tavily-api-key"  # Обязательно: API-ключ Tavily
  tavily_api_base_url: "https://api.tavily.com"  # URL API Tavily
  content_limit: 1500  # Лимит символов содержимого на источник (обрезает извлечённое содержимое)
```

**Пример:**

```yaml
agents:
  research_agent:
    search:
      content_limit: 2000  # Увеличить лимит содержимого для более детального извлечения
    tools:
      - "WebSearchTool"
      - "ExtractPageContentTool"
```

## Конфигурация тулов в агентах

Тулы настраиваются для каждого агента в файле `agents.yaml` или определениях агентов:

```yaml
agents:
  my_agent:
    base_class: "SGRAgent"
    tools:
      - "WebSearchTool"
      - "ExtractPageContentTool"
      - "CreateReportTool"
      - "ClarificationTool"
      - "GeneratePlanTool"
      - "AdaptPlanTool"
      - "FinalAnswerTool"
    execution:
      max_clarifications: 3
      max_iterations: 10
    search:
      max_searches: 4
      max_results: 10
      content_limit: 1500
```

### Управление доступностью тулов

Агенты автоматически фильтруют доступные тулы на основе лимитов выполнения:

- После `max_iterations`: Доступны только `CreateReportTool` и `FinalAnswerTool`
- После `max_clarifications`: `ClarificationTool` удаляется
- После `max_searches`: `WebSearchTool` удаляется

Это гарантирует, что агенты завершают задачи в рамках настроенных лимитов.

## MCP-тулы

Тулы также могут создаваться из MCP (Model Context Protocol) серверов. Эти тулы наследуются от `MCPBaseTool` и автоматически генерируются из схем MCP-сервера.

**Исходный код:** [sgr_agent_core/base_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/base_tool.py) (класс MCPBaseTool)

**Конфигурация:**

```yaml
mcp:
  mcpServers:
    deepwiki:
      url: "https://mcp.deepwiki.com/mcp"
    your_server:
      url: "https://your-mcp-server.com/mcp"
      headers:
        Authorization: "Bearer your-token"
```

**Поведение:**

- MCP-тулы автоматически преобразуются в экземпляры BaseTool
- Схемы тулов генерируются из входных схем MCP-сервера
- Выполнение вызывает MCP-сервер с полезной нагрузкой тула
- Ответ ограничен `execution.mcp_context_limit`

**Конфигурация:**

```yaml
execution:
  mcp_context_limit: 15000  # Максимальная длина контекста из ответа MCP-сервера
```

## Реестр тулов

Все тулы автоматически регистрируются в `ToolRegistry` при определении. На тулы можно ссылаться по имени в конфигурациях агентов.

**Исходный код:** [sgr_agent_core/services/registry.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/services/registry.py)

Тулы регистрируются с их `tool_name` (автоматически генерируется из имени класса, если не указано). Пользовательские тулы должны быть импортированы до создания агента для регистрации.

## Набор тулов по умолчанию

Набор тулов по умолчанию включает все стандартные тулы:

**Исходный код:** [sgr_deep_research/default_definitions.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_deep_research/default_definitions.py)

```python
DEFAULT_TOOLKIT = [
    ClarificationTool,
    GeneratePlanTool,
    AdaptPlanTool,
    FinalAnswerTool,
    WebSearchTool,
    ExtractPageContentTool,
    CreateReportTool,
]
```

ReasoningTool добавляется отдельно для SGR-агентов, которым требуются явные фазы рассуждения.
