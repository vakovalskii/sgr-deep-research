## 🧶 Последовательность выполнения агента

На следующей диаграмме показан полный рабочий процесс SGR агента с поддержкой прерывания и уточнений:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Server
    participant Agent as SGR Agent
    participant LLM as LLM
    participant Tools as Research Tools

    Note over Client, Tools: SGR Agent Core - Рабочий процесс агента

    Client->>API: POST /v1/chat/completions<br/>{"model": "sgr_agent", "messages": [...]}

    API->>Agent: Создать новый SGR Agent<br/>с уникальным ID
    Note over Agent: Состояние: INITED

    Agent->>Agent: Инициализировать контекст<br/>и историю разговора

    loop Цикл рассуждений SGR (макс. 6 шагов)
        Agent->>Agent: Подготовить инструменты на основе<br/>текущих ограничений контекста
        Agent->>LLM: Запрос структурированного вывода<br/>со схемой NextStep

        LLM-->>API: Потоковые чанки
        API-->>Client: SSE поток с<br/>agent_id в поле model

        LLM->>Agent: Распарсенный результат NextStep

        alt Инструмент: Clarification
            Note over Agent: Состояние: WAITING_FOR_CLARIFICATION
            Agent->>Tools: Выполнить инструмент уточнения
            Tools->>API: Вернуть уточняющие вопросы
            API-->>Client: Поток уточняющих вопросов<br/>(содержит agent_id в тексте)

            alt Режим stateless (клиент шлёт полный контекст)
                Client->>API: POST /v1/chat/completions<br/>{"model": "sgr_agent", "messages": [<br/>  ..., "agent {id} started", ...]}<br/>ID агента найден внутри messages
                API->>Agent: provide_clarification(replace=True)<br/>Разговор полностью заменяется
            else Режим stateful (клиент шлёт дельту)
                Client->>API: POST /v1/chat/completions<br/>{"model": "agent_id", "messages": [новые ответы]}
                API->>Agent: provide_clarification(replace=False)<br/>Сообщения дописываются к разговору
            end
            Note over Agent: Состояние: RESEARCHING

        else Инструмент: GeneratePlan
            Agent->>Tools: Выполнить генерацию плана
            Tools->>Agent: План исследования создан

        else Инструмент: WebSearch
            Agent->>Tools: Выполнить веб-поиск
            Tools->>Tools: Вызов Tavily API
            Tools->>Agent: Результаты поиска + источники
            Agent->>Agent: Обновить контекст источниками

        else Инструмент: AdaptPlan
            Agent->>Tools: Выполнить адаптацию плана
            Tools->>Agent: Обновленный план исследования

        else Инструмент: CreateReport
            Agent->>Tools: Выполнить создание отчета
            Tools->>Tools: Сгенерировать комплексный<br/>отчет с цитатами
            Tools->>Agent: Финальный отчет исследования

        else Инструмент: ReportCompletion
            Note over Agent: Состояние: COMPLETED
            Agent->>Tools: Выполнить завершение
            Tools->>Agent: Статус завершения задачи
        end

        Agent->>Agent: Добавить результат инструмента в<br/>историю разговора
        API-->>Client: Поток результата выполнения инструмента

        break Задача завершена
            Agent->>Agent: Прервать цикл выполнения
        end
    end

    Agent->>API: Завершить поток
    API-->>Client: Закрыть SSE поток

    Note over Client, Tools: Агент остается доступным<br/>через agent_id для дальнейших уточнений<br/>или отмены через DELETE /agents/{agent_id}
```

!!! Note "Отмена выполнения агента"
    В любой момент во время выполнения агент может быть отменен с помощью endpoint `DELETE /agents/{agent_id}`.
    Это остановит задачу выполнения, установит состояние агента в `CANCELLED` и удалит его из хранилища.

## 🤖 Возможности Schema-Guided Reasoning:

1. **🤔 Clarification** - уточняющие вопросы при неясности
2. **📋 Plan Generation** - создание плана исследования
3. **🔍 Web Search** - поиск информации в интернете
4. **🔄 Plan Adaptation** - адаптация плана на основе результатов
5. **📝 Report Creation** - создание детального отчета
6. **✅ Final Answer** - завершение задачи
