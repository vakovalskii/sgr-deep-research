SGR Agent Core предоставляет полноценный REST API, который полностью совместим с форматом API OpenAI, что упрощает интеграцию с существующими приложениями.

## Базовый URL

```
http://localhost:8010
```

## Документация API

Интерактивная документация API (Swagger UI) доступна по адресу `http://localhost:8010/docs`. Вы можете изучить все эндпоинты, протестировать запросы и просмотреть схемы запросов/ответов прямо в браузере.

## Аутентификация

Аутентификация не поддерживается API. Для продакшн развертываний используйте reverse proxy с настроенной аутентификацией.

## GET `/health`

Проверить, работает ли API и находится ли он в рабочем состоянии.

**Запрос:**

```bash
curl http://localhost:8010/health
```

**Ответ:**

```json
{
  "status": "healthy",
  "service": "SGR Agent Core API"
}
```

**Поля ответа:**

- `status` (string, literal: "healthy"): Всегда возвращает "healthy" когда API работает
- `service` (string): Идентификатор названия сервиса

## GET `/v1/models`

Получить список доступных моделей агентов. Возвращает все определения агентов, настроенные в системе.

**Доступные модели:**

- `sgr_agent` - Чистый SGR (Schema-Guided Reasoning)
- `sgr_tool_calling_agent` - SGR + Function Calling гибрид
- `tool_calling_agent` - Чистый Function Calling

**Запрос:**

```bash
curl http://localhost:8010/v1/models
```

**Ответ:**

```json
{
  "data": [
    {
      "id": "sgr_agent",
      "object": "model",
      "created": 1234567890,
      "owned_by": "sgr-agent-core"
    },
    {
      "id": "sgr_tool_calling_agent",
      "object": "model",
      "created": 1234567890,
      "owned_by": "sgr-agent-core"
    }
  ],
  "object": "list"
}
```

**Поля ответа:**

- `data` (array): Список доступных моделей агентов
  - `id` (string): Идентификатор модели агента (совпадает с именем определения агента)
  - `object` (string, literal: "model"): Идентификатор типа объекта
  - `created` (integer): Заглушка временной метки (для совместимости с OpenAI)
  - `owned_by` (string): Всегда "sgr-agent-core"
- `object` (string, literal: "list"): Идентификатор типа ответа

## POST `/v1/chat/completions`

Создать завершение чата для исследовательских задач. Это основной endpoint для взаимодействия с SGR агентами. Создает новый экземпляр агента и запускает его выполнение асинхронно.

**Тело запроса:**

```json
{
  "model": "sgr_agent",
  "messages": [
    {
      "role": "user",
      "content": "Research BMW X6 2025 prices in Russia"
    }
  ],
  "stream": true,
  "max_tokens": 1500,
  "temperature": 0.4
}
```

**Параметры запроса:**

- `model` (string, обязательный, по умолчанию: "sgr_tool_calling_agent"): Имя типа агента (например, "sgr_agent", "sgr_tool_calling_agent") или существующий ID агента для запросов на уточнение
- `messages` (array, обязательный): Список сообщений чата в формате OpenAI (ChatCompletionMessageParam). Поддерживает:
  - Текстовые сообщения: `{"role": "user", "content": "текст"}`
  - Мультимодальные сообщения: `{"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}}]}`
  - Системные сообщения: `{"role": "system", "content": "..."}`
- `stream` (boolean, обязательный, по умолчанию: true): **Должно быть `true`** - поддерживаются только потоковые ответы
- `max_tokens` (integer, опциональный, по умолчанию: 1500): Максимальное количество токенов для генерации
- `temperature` (float, опциональный, по умолчанию: 0): Температура генерации (0.0-1.0). Меньшие значения делают вывод более детерминированным

**Особое поведение - Запросы на уточнение:**

Если `model` содержит ID агента (формат: `{agent_name}_{uuid}`) и агент находится в состоянии `waiting_for_clarification`, этот endpoint автоматически перенаправит запрос на обработчик уточнений вместо создания нового агента.

**Ответ:**

**Заголовки ответа:**

- `X-Agent-ID` (string): Уникальный идентификатор агента (формат: `{agent_name}_{uuid}`)
- `X-Agent-Model` (string): Имя модели агента
- `Cache-Control`: `no-cache`
- `Connection`: `keep-alive`
- `Content-Type`: `text/event-stream`

**Формат потокового ответа:**

Ответ передается как Server-Sent Events (SSE) с обновлениями в реальном времени. Каждое событие следует формату, совместимому с OpenAI:

```
data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"sgr_agent","choices":[{"index":0,"delta":{"content":"..."},"finish_reason":null}]}

data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"sgr_agent","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Ошибки:**

- `400 Bad Request`: Неверное имя модели или некорректный запрос
  ```json
  {
    "detail": "Invalid model 'invalid_model'. Available models: ['sgr_agent', 'sgr_tool_calling_agent']"
  }
  ```
- `501 Not Implemented`: Непотоковый запрос (stream должен быть true)
  ```json
  {
    "detail": "Only streaming responses are supported. Set 'stream=true'"
  }
  ```

**Запрос:**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
    "messages": [{"role": "user", "content": "Research AI market trends"}],
    "stream": true,
    "temperature": 0
  }'
```

**Запрос с изображением (URL):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Проанализируй этот график и исследуй тренды"},
        {"type": "image_url", "image_url": {"url": "https://example.com/chart.png"}}
      ]
    }],
    "stream": true
  }'
```

**Запрос с изображением (Base64):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Что показано на этом изображении?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."}}
      ]
    }],
    "stream": true
  }'
```

**Примечание:** Base64 URL изображений длиннее 200 символов будут обрезаны в ответах для оптимизации производительности.

## GET `/agents`

Получить список всех активных агентов, хранящихся в памяти. Возвращает пустой список, если активных агентов нет.

**Запрос:**

```bash
curl http://localhost:8010/agents
```

**Ответ:**

```json
{
  "agents": [
    {
      "agent_id": "sgr_agent_12345-67890-abcdef",
      "task_messages": [
        {
          "role": "user",
          "content": "Research BMW X6 2025 prices"
        }
      ],
      "state": "researching",
      "creation_time": "2025-01-27T12:00:00"
    }
  ],
  "total": 1
}
```

**Поля ответа:**

- `agents` (array): Список элементов агентов
  - `agent_id` (string): Уникальный идентификатор агента (формат: `{agent_name}_{uuid}`)
  - `task_messages` (array): Исходные сообщения задачи в формате OpenAI
  - `state` (string): Текущее состояние агента (см. Состояния агента ниже)
  - `creation_time` (string, ISO 8601): Временная метка создания агента
- `total` (integer): Общее количество агентов в хранилище

**Состояния агента:**

- `inited` - Агент инициализирован, готов к запуску
- `researching` - Агент активно исследует и выполняет задачи
- `waiting_for_clarification` - Агенту требуется уточнение от пользователя для продолжения
- `completed` - Исследование успешно завершено
- `cancelled` - Выполнение агента было отменено
- `failed` - Выполнение агента завершилось с ошибкой
- `error` - Произошла ошибка выполнения агента

## GET `/agents/{agent_id}/state`

Получить детальную информацию о состоянии конкретного агента. Возвращает полную информацию о текущем состоянии выполнения агента, прогрессе и контексте.

**Параметры пути:**

- `agent_id` (string, обязательный): Уникальный идентификатор агента (формат: `{agent_name}_{uuid}`)

**Запрос:**

```bash
curl http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/state
```

**Ответ:**

```json
{
  "agent_id": "sgr_agent_12345-67890-abcdef",
  "task_messages": [
    {
      "role": "user",
      "content": "Research BMW X6 2025 prices"
    }
  ],
  "state": "researching",
  "iteration": 3,
  "searches_used": 2,
  "clarifications_used": 0,
  "sources_count": 5,
  "current_step_reasoning": {
    "action": "web_search",
    "query": "BMW X6 2025 price Russia",
    "reason": "Need current market data"
  },
  "execution_result": null
}
```

**Поля ответа:**

- `agent_id` (string): Уникальный идентификатор агента
- `task_messages` (array): Исходные сообщения задачи в формате OpenAI
- `state` (string): Текущее состояние агента (см. Состояния агента в GET `/agents`)
- `iteration` (integer): Номер текущей итерации (начинается с 0)
- `searches_used` (integer): Количество выполненных веб-поисков на данный момент
- `clarifications_used` (integer): Количество запросов на уточнение
- `sources_count` (integer): Общее количество собранных уникальных источников
- `current_step_reasoning` (object | null): Данные рассуждений текущего шага (структура зависит от типа агента)
- `execution_result` (string | null): Финальный результат выполнения, если агент завершен, иначе null

**Ошибки:**

- `404 Not Found`: Агент не найден в хранилище
  ```json
  {
    "detail": "Agent not found"
  }
  ```

## POST `/agents/{agent_id}/provide_clarification`

Предоставить уточнение агенту, который ожидает ввода. Возобновляет выполнение агента после получения сообщений уточнения.

**Параметры пути:**

- `agent_id` (string, обязательный): Уникальный идентификатор агента (формат: `{agent_name}_{uuid}`)

**Тело запроса:**

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Focus on luxury models only, price range 5-8 million rubles"
    }
  ]
}
```

**Параметры запроса:**

- `messages` (array, обязательный): Сообщения уточнения в формате OpenAI (ChatCompletionMessageParam). Может содержать несколько сообщений для сложных уточнений.

**Запрос:**

```bash
curl -X POST "http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}]
  }'
```

**Ответ:**

**Заголовки ответа:**

- `X-Agent-ID` (string): Уникальный идентификатор агента
- `Cache-Control`: `no-cache`
- `Connection`: `keep-alive`
- `Content-Type`: `text/event-stream`

**Потоковый ответ:**

Возвращает потоковый ответ (формат SSE) с продолжением исследования после уточнения. Агент возобновляет выполнение с точки, где он запросил уточнение.

**Ошибки:**

- `404 Not Found`: Агент не найден в хранилище
  ```json
  {
    "detail": "Agent not found"
  }
  ```
- `500 Internal Server Error`: Ошибка при обработке уточнения
  ```json
  {
    "detail": "Сообщение об ошибке"
  }
  ```

**Примечание:** Этот endpoint также доступен через POST `/v1/chat/completions`, используя ID агента в качестве параметра `model`, когда агент находится в состоянии `waiting_for_clarification`.

## DELETE `/agents/{agent_id}`

Отменить выполнение запущенного агента и удалить его из хранилища. Если агент в данный момент выполняется, он будет сначала отменен, а затем удален.

**Параметры пути:**

- `agent_id` (string, обязательный): Уникальный идентификатор агента (формат: `{agent_name}_{uuid}`)

**Запрос:**

```bash
curl -X DELETE "http://localhost:8010/agents/sgr_agent_12345-67890-abcdef"
```

**Ответ:**

```json
{
  "agent_id": "sgr_agent_12345-67890-abcdef",
  "deleted": true,
  "final_state": "cancelled"
}
```

**Поля ответа:**

- `agent_id` (string): ID удаленного агента
- `deleted` (boolean): Всегда `true` при успешном удалении
- `final_state` (string): Финальное состояние агента после удаления. Возможные значения:
  - `"cancelled"` - Агент выполнялся и был отменен
  - `"completed"` - Агент уже был завершен
  - `"failed"` - Агент был в состоянии ошибки
  - `"error"` - Агент был в состоянии ошибки выполнения
  - Другие состояния, если агент был в другом состоянии

**Поведение:**

- Если агент в данный момент выполняется, вызывается `agent.cancel()` сначала
- Задача выполнения агента останавливается асинхронно
- Состояние агента сохраняется в `final_state` перед удалением
- Агент удаляется из хранилища после отмены/удаления
- Работает для агентов в любом состоянии (выполняется, завершен, ошибка и т.д.)

**Ошибки:**

- `404 Not Found`: Агент не найден в хранилище
  ```json
  {
    "detail": "Agent not found"
  }
  ```

**Случаи использования:**

- Остановить долго выполняющуюся исследовательскую задачу, которая больше не нужна
- Очистить хранилище от завершенных агентов
- Отменить агента, который завис или выполняется слишком долго
- Освободить ресурсы, удалив неактивных агентов
