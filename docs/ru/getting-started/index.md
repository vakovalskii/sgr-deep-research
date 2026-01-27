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

### Запуск с Docker

Самый быстрый способ начать работу — использовать Docker:

```bash
# Клонируем репозиторий
git clone https://github.com/vamplabai/sgr-agent-core.git
cd sgr-agent-core

# Делаем папки с правами на запись для всех
sudo mkdir -p logs reports
sudo chmod 777 logs reports

# Копируем и редактируем файл конфигурации
cp examples/sgr_deep_research/config.yaml.example examples/sgr_deep_research/config.yaml
# Отредактируйте examples/sgr_deep_research/config.yaml и установите ваши API ключи

# Запускаем контейнер
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

API сервер будет доступен по адресу `http://localhost:8010`. Интерактивная документация API (Swagger UI) доступна по адресу `http://localhost:8010/docs`.

### Установка

Если вы хотите использовать SGR Agent Core как Python библиотеку (фреймворк):

```bash
pip install sgr-agent-core
```

См. [Руководство по установке](installation.md) для подробных инструкций и [Использование как библиотека](../framework/first-steps.md) для начала работы.

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

### Использование как библиотека

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
- **[Использование как библиотека](../framework/first-steps.md)** — Узнайте, как использовать SGR Agent Core как Python библиотеку
- **[Быстрый старт API сервера](../sgr-api/SGR-Quick-Start.md)** — Начните работу с REST API сервисом

## Контакты и сообщество

**По вопросам сотрудничества**: [@VaKovaLskii](https://t.me/neuraldeep)

**Чат сообщества**: Отвечаем на вопросы в [Telegram чате](https://t.me/sgragentcore) (ru/en)

![](../../assets/images/rmr750x200.png)

Проект разрабатывается с поддержкой команды AI R&D в red_mad_robot, которая предоставляет исследовательские ресурсы, инженерную экспертизу, инфраструктуру и операционную поддержку.

Узнайте больше о red_mad_robot: [redmadrobot.ai](https://redmadrobot.ai/)↗️ [habr](https://habr.com/ru/companies/redmadrobot/articles/)↗️ [telegram](https://t.me/Redmadnews/)↗️
