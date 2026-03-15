# Highlights

Эта страница отвечает на простой вопрос: **Чего крутого мы заложили во фреймворк**.
Здесь — короткие кейсы и интуитивные примеры; за более полной и строгой документацией лучше идти в:

- [Основные концепции](framework/main-concepts.md)
- [Руководство по конфигурации](framework/configuration.md)
- [Getting Started](getting-started/index.md)

---

## 1. Что это?

SGR agent core — это **фреймворк-платформа для построения и запуска ИИ‑агентов**, реализующая идеи нашей команды о том, как строить, изучать и применять агентные технологии от исследований до production пайплайнов.

Центральной идеей заложена Schema Guided Reasoning - такой подход позволяет получать детерминированные, интерпретируемые результаты на множестве LLM от больших 70B+и до 7b(с оговорками) или MoE 20b. Мы высоко ценим возможность получения стабильных результатов для каждого шага агента, пригодных для отображения и переиспользования, интеграции в классические кодовые системы.

**Мы не стремимся создавать систему, которая могла бы делать всё и сразу** </br>
Фреймворк даёт достаточные для быстрого старта возможности описать и запустить агента. А так же набор абстракций (`BaseAgent`, `BaseTool`, `BaseStreamingGenerator` etc) для дальнейшего погружения в область,  кастомизации системы под собственные нужды.

Кроме того в `/examples` наша команда и другие разработчики описываем на практике более продвинутые/специфические технологии агентов. Например:

- **[Progressive Tool Discovery](https://github.com/vamplabai/sgr-agent-core/tree/main/examples/progressive_discovery)** — как работать с 50++ тулами
- **[SGR File Agent](https://github.com/vamplabai/sgr-agent-core/tree/main/examples/sgr_file_agent)** — поиск файлов по паттерну/дате/размеру, чтение, grep по содержимому
- **[Research with Images](https://github.com/vamplabai/sgr-agent-core/tree/main/examples/research_with_images)** — мультимодальный запрос к агенту

А теперь более наглядно

**Мини‑пример: напрямую создать и инициализировать агента**

```python
import asyncio

from openai import AsyncOpenAI

from sgr_agent_core import AgentConfig
from sgr_agent_core.agents.sgr_agent import SGRAgent
from sgr_agent_core.tools.final_answer_tool import FinalAnswerTool


async def main() -> None:
    client = AsyncOpenAI(api_key="YOUR_OPENAI_API_KEY")

    # 3. Напрямую создаём экземпляр SGRAgent
    agent = SGRAgent(
        task_messages=[
            {"role": "user", "content": "Собери краткий обзор по теме RAG-систем"},
        ],
        openai_client=client,
        agent_config=AgentConfig(),
        toolkit=[FinalAnswerTool],
    )

    # 4. Запускаем цикл работы агента и получаем результат
    result = await agent.execute()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

Идея: вы описываете агента (в коде или в config файле) и запускаете его под конкретную задачу.

---

## 2. Как этим пользоваться

### Вы разработчик, создающий собственных агнтов.

**-->RTFM**

- ставите пакет `sgr-agent-core`;
- читаете разделы про [конфигурацию](framework/configuration.md) и [основные концепции](framework/main-concepts.md);
- описываете агентов через `config.yaml` и `agents.yaml` (или в любом другом удобном виде);
- в коде расширяете базовые сущности под нужную вам логику агента, его тулов
- вызываете `execute()`.

**Мини‑пример: создать агента из конфигов и запустить**

```python
from sgr_agent_core import GlobalConfig, AgentFactory

config = GlobalConfig.from_yaml("config.yaml")
config.definitions_from_yaml("agents.yaml")

researcher_def = config.agents["researcher"]
agent = await AgentFactory.create(
    researcher_def,
    task_messages=[{"role": "user", "content": "Найди свежие статьи про multi-agent системы"}],
)
await agent.execute()
```

### Вы хотите воспользоваться готовым решением


Можно мыслить так: **«есть один YAML, который описывает, что надо делать»** прям как docker compose

1. Берёте готовый конфиг из `/examples`, у коллег, из интернета (но это не безопасно) или пишете свой `config.yaml`.
2. Кладёте его в свой проект
3. Запускаете сервер:

    ```bash
    sgr -c config.yaml
    ```

4. Поднимается API — по умолчанию на `http://localhost:8010`, Swagger доступен по адресу `http://localhost:8010/docs`.
5. Отправляете запрос по схеме (совместимо с OpenAI chat/completions протоколом)
Подробнее — в [Быстрый старт API сервера](sgr-api/SGR-Quick-Start.md).

---

## 3. Как получить информацию от агента?

Есть два варианта:

### Запустить, подождать и посмотреть результат

- создаёте агента;
- запускаете `execute()`;
- забираете итоговый результат

**Мини‑пример: получить финальный результат из контекста агента**

```python
result = await agent.execute()

print(result)

# или получить напрямую из контекста
print(agent._context.execution_result)
```

Это удобно, когда важен только конечный ответ, а не процесс.

### Запустить и подключиться к стриму — смотреть, что происходит

- включаете потоковый режим при запуске;
- подключаетесь к стриму и обрабатываете события по мере поступления;
- можете строить интерфейсы с «живым» ходом работы агента.

**Мини‑пример: запрос к API с включённым стримингом**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
    "messages": [
      {"role": "user", "content": "Исследуй рынок RAG-систем и сделай краткий вывод"}
    ],
    "stream": true
  }'
```

Ответ придёт в формате Server‑Sent Events: вы можете читать поток построчно и обновлять UI или логи в реальном времени.

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":""},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"tool_calls":[{"index":0,"id":"1-reasoning","type":"function","function":{"name":"reasoning_tool","arguments":""}}]},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"reasoning_steps\":[\"Нужно найти актуальные данные по рынку RAG\"],\"plan_status\":\"В процессе\"}"}}]},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"tool_calls":[{"index":0,"id":"1-action","type":"function","function":{"name":"web_search_tool","arguments":"{\"query\":\"RAG systems market 2025\"}"}}]},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Рынок RAG-систем в 2025 году..."}},"index":0}]}

data: [DONE]
```

---

## 4. Как посмотреть на агента в красивом интерфейсе?

Можно подключить [Open WebUI](https://github.com/open-webui/open-webui): он понимает OpenAI-совместимый API из коробки. Укажите адрес сервера — и получите полноценный чат-интерфейс с историей, переключением между агентами и стримингом без единой строки фронтенд-кода.

```bash
docker run -d \
  -p 3000:8080 \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:8010/v1 \
  -e OPENAI_API_KEY=dummy \
  ghcr.io/open-webui/open-webui:main
```

После запуска откройте `http://localhost:3000` — агенты из вашего конфига появятся в списке моделей.

![Open WebUI с SGR агентом](../assets/images/openwebui_example.png)

> **Важно:** при подключении к Open WebUI необходимо сменить стриминг-адаптер В `config.yaml` укажите:
> ```yaml
> execution:
>   streaming_generator: "open_webui"  # вместо "openai" по умолчанию
> ```

---

## 5. Как построить много агентов?

Фреймворк использует **двухуровневую систему конфигурации** на основе `GlobalConfig` и `AgentDefinition`, `ToolDefinition`. На практике это означает:

- один базовый `config.yaml` с общими настройками (модель, лимиты, директории логов и отчётов);
- один или несколько файлов с описанием агентов (`agents.yaml`, `more_agents.yaml` и т.п.).
- upd: При желании как общий конфиг, так и конфиги агентов можно определить в одном файлике

Проще всего думать так:

- действуем просто — делаем один конфиг и одного универсального агента;
- действуем сложнее — прописываем каждого агента с отдельными ролями и инструментами., наследуя какие-то общие параметры из базового конфига

> Мы находим конфигурацию на основе yaml файлов крутым способом избежать большого количества лишнего кода, наследований, импортов и прочих  проблем с организацией ваших (и наших) проектов. Все основные модули идейно сделаны так, чтобы можно было легко указать на пользовательские  модели и классы, накинуть своих параметров/настроек, просто дописав их к существующим.


**Мини‑пример: два разных агента в `agents.yaml`**

```yaml
agents:
  researcher:
    base_class: "IronAgent"
    llm:
      model: "gpt-4o"
    tools:
      - "web_search_tool"
      - "extract_page_content_tool"
      - "create_report_tool"
      - "final_answer_tool"

  planner:
    base_class: "SGRToolCallingAgent"
    llm:
      model: "gpt-4o-mini"
    tools:
      - "generate_plan_tool"
      - "adapt_plan_tool"
      - "final_answer_tool"
```
Подробная схема конфигурации и примеры уже описаны в [Configuration Guide](framework/configuration.md).

---

## 6. Как понять, что что‑то пошло не так?

Фреймворк строится вокруг **обязательной валидации создаваемых агентом сущностей**:

- на каждом шаге создаются объекты по заранее описанным схемам;
- результат проверяется перед тем, как идти дальше;
- при несоответствии схемам выполнение завершается с явной ошибкой, а не «тихим» неопределённым ответом.

Это значит:

- Вы либо получаете валидные данные, либо понятную ошибку;
- Видно, на каком шаге и в какой части пайплайна что‑то пошло не так;

**Мини‑пример: отловить ошибку и посмотреть состояние агента**

```python
from sgr_agent_core import AgentStatesEnum

try:
    await agent.execute()
except Exception as exc:
    print(f"Agent failed: {exc}")
    print("State:", agent._context.state)
    if agent._context.state in {AgentStatesEnum.ERROR, AgentStatesEnum.FAILED}:
        print("Execution result:", agent._context.execution_result)
```

Если что‑то идёт не так, это видно по состоянию и исключению, а не по случайной «галлюцинации» в тексте.
**Ловите исключения, закидывайте в системы телеметрии, отправляйте более стабильных агентов разбираться с менее стабильными**

---

## 7. Что если используемая модель не совместима / недостаточно умна для агентных задач

SGR методология позволяет строить reasoning формат рассуждения даже в случае, если модель сама по себе этого не умеет. Наш [бенчмарк](https://github.com/vamplabai/sgr-agent-core/tree/main/benchmark) показал, что `gpt-4.1-mini` с фреймворком набирает **Accuracy = 0.861** на SimpleQA — конкурентоспособный результат даже по меркам более крупных решений.

Если модель вообще не поддерживает tool calling или structured output — есть **`IronAgent`**: работает с сырым ответом модели, сам вытаскивает имя инструмента и параметры, при неудаче делает retry.

Точный ответ для вашей конкретной модели и задачи — только в ходе замеров.

---

## 8. У меня офигительная идея для продукта на миллион, но фреймворк её не поддерживает

Фреймворк задуман как база, на которой можно строить собственные сложные решения.

Вариантов расширения несколько:

- наследоваться от базовых классов `BaseAgent`, `BaseTool`, `BaseStreamingGenerator` и добавлять своё поведение;
- описывать новые агенты и инструменты через конфиги, используя уже существующие реализации;
- комбинировать оба подхода: своя логика в коде плюс декларативные настройки в YAML/JSON.

Регистры и конфигурация делают это достаточно прозрачным:

- новые агенты и тулы регистрируются и становятся доступны по имени;
- конфигурация позволяет подменять или дополнять поведение без жёстких привязок в коде.

**Мини‑пример: свой тул и агент, использующий его**

```python
from sgr_agent_core import BaseTool, AgentConfig, AgentDefinition, AgentFactory
from sgr_agent_core import AgentContext
from sgr_agent_core.agents.tool_calling_agent import ToolCallingAgent
from sgr_agent_core.tools import GeneratePlanTool, FinalAnswerTool


class SummarizeNotesTool(BaseTool):
    """Summarize raw notes into a short summary."""

    text: str

    async def __call__(self, context: AgentContext, config: AgentConfig) -> str:
        # Здесь могла бы быть интеграция с вашей системой или моделью
        return self.text[:200]


custom_config = AgentConfig(
    tools=[GeneratePlanTool, SummarizeNotesTool, FinalAnswerTool],
)

custom_def = AgentDefinition(
    name="notes_summarizer",
    base_class=ToolCallingAgent,
    **custom_config.model_dump(),
)

agent = await AgentFactory.create(
    custom_def,
    task_messages=[
        {"role": "user", "content": "Сожми мои заметки в короткое резюме"},
    ],
)
```

Можно начать с таких простых расширений, а затем вырастить на их основе полноценную систему с несколькими агентами и богатой конфигурацией.
*Если идея настолько крутая, можно написать нам или в комьюнити - сориентируем =)*
