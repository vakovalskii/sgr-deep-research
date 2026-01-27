# SGR Agent Core

**SGR Agent Core** — это open-source фреймворк для создания интеллектуальных исследовательских агентов с использованием Schema-Guided Reasoning (SGR). Проект предоставляет основную библиотеку с расширяемым интерфейсом `BaseAgent`, реализующим трёхфазную архитектуру, и несколько готовых реализаций исследовательских агентов, построенных на её основе.

Библиотека включает расширяемые инструменты для поиска, рассуждений и уточнений, ответы в реальном времени через стриминг и REST API, совместимый с OpenAI. Работает с любыми LLM, совместимыми с OpenAI, включая локальные модели для полностью приватных исследований.

## Почему стоит использовать SGR Agent Core?

* **Schema-Guided Reasoning** — SGR сочетает структурированные рассуждения с гибким выбором инструментов
* **Множество типов агентов** — Выберите из `SGRAgent`, `ToolCallingAgent` или `SGRToolCallingAgent`
* **Расширяемая архитектура** — Легко создавать собственные агенты и инструменты
* **Совместимый с OpenAI API** — Прямая замена для эндпоинтов OpenAI API
* **Стриминг в реальном времени** — Встроенная поддержка потоковых ответов через SSE
* **Готов к продакшену** — Проверен в бою с комплексным покрытием тестами и поддержкой Docker

## Быстрый старт

### Установка

Установите SGR Agent Core через pip:

```bash
pip install sgr-agent-core
```

Или используйте Docker:

```bash
docker pull ghcr.io/vamplabai/sgr-agent-core:latest
```

См. [Руководство по установке](installation.md) для подробных инструкций.

### CLI утилита (`sgrsh`)

После установки вы можете использовать утилиту командной строки `sgrsh` для интерактивной работы с агентами:

```bash
# Режим одного запроса
sgrsh "Найди текущую цену биткоина"

# С выбором агента
sgrsh --agent sgr_agent "Что такое AI?"

# С указанием файла конфигурации
sgrsh -c config.yaml -a sgr_agent "Ваш запрос"

# Интерактивный режим чата (без аргумента запроса)
sgrsh
sgrsh -a sgr_agent
```

Команда `sgrsh`:
- Автоматически ищет `config.yaml` в текущей директории
- Поддерживает интерактивный режим чата для множественных запросов
- Обрабатывает запросы на уточнение от агентов интерактивно
- Работает с любым агентом, определённым в вашей конфигурации

### Быстрый пример

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
        task_messages=[{"role": "user", "content": "Исследуй тренды в AI"}],
    )

    result = await agent.execute()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

## Документация

- **[Установка](installation.md)** — Подробные инструкции по установке через pip и Docker
- **[Agent Core Framework](../framework/main-concepts.md)** — Поймите основные концепции и архитектуру
- **[SGR API Service](../sgr-api/SGR-Quick-Start.md)** — Начните работу с REST API сервисом

## Контакты и сообщество

**По вопросам сотрудничества**: [@VaKovaLskii](https://t.me/neuraldeep)

**Чат сообщества**: Отвечаем на вопросы в [Telegram чате](https://t.me/sgragentcore) (ru/en)

![](../../assets/images/rmr750x200.png)

Проект разрабатывается с поддержкой команды AI R&D в red_mad_robot, которая предоставляет исследовательские ресурсы, инженерную экспертизу, инфраструктуру и операционную поддержку.

Узнайте больше о red_mad_robot: [redmadrobot.ai](https://redmadrobot.ai/)↗️ [habr](https://habr.com/ru/companies/redmadrobot/articles/)↗️ [telegram](https://t.me/Redmadnews/)↗️
