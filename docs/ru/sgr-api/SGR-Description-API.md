SGR Agent Core предоставляет полноценный REST API, который полностью совместим с форматом API OpenAI, что упрощает интеграцию с существующими приложениями.

## 🔍 Базовый URL

```
http://localhost:8010
```

## 🔍 Аутентификация

Аутентификация не требуется для локальной разработки. Для продакшн развертываний настройте аутентификацию по необходимости.

______________________________________________________________________

<details>
<summary><strong>🏥 Health Check</strong> - Проверка статуса и доступности API</summary>

## 🔍 GET `/health`

Проверить, работает ли API и находится ли он в рабочем состоянии.

**Ответ:**

```json
{
  "status": "healthy",
  "service": "sgr-agent-core API"
}
```

**Пример:**

```bash
curl http://localhost:8010/health
```

</details>

______________________________________________________________________

<details>
<summary><strong>🤖 Доступные модели</strong> - Получить список поддерживаемых моделей агентов</summary>

## 🔍 GET `/v1/models`

Получить список доступных моделей агентов.

**Ответ:**

```json
{
  "data": [
    {
      "id": "sgr-agent",
      "object": "model",
      "created": 1234567890,
      "owned_by": "sgr-deep-research"
    },
    {
      "id": "sgr-tools-agent",
      "object": "model",
      "created": 1234567890,
      "owned_by": "sgr-deep-research"
    }
  ],
  "object": "list"
}
```

**Доступные модели:**

- `sgr-agent` - Чистый SGR (Schema-Guided Reasoning)
- `sgr-tools-agent` - SGR + Function Calling гибрид
- `sgr-auto-tools-agent` - SGR + Auto Function Calling
- `sgr-so-tools-agent` - SGR + Structured Output
- `tools-agent` - Чистый Function Calling

**Пример:**

```bash
curl http://localhost:8010/v1/models
```

</details>

______________________________________________________________________

<details>
<summary><strong>💬 Chat Completions</strong> - Основной endpoint для исследований с поддержкой потоковой передачи</summary>

## 🔍 POST `/v1/chat/completions`

Создать завершение чата для исследовательских задач. Это основной endpoint для взаимодействия с SGR агентами.

**Тело запроса:**

```json
{
  "model": "sgr-agent",
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

**Параметры:**

- `model` (string, обязательный): Тип агента или существующий ID агента
- `messages` (array, обязательный): Список сообщений чата в формате OpenAI (ChatCompletionMessageParam)
- `stream` (boolean, по умолчанию: true): Включить режим потоковой передачи
- `max_tokens` (integer, опциональный): Максимальное количество токенов
- `temperature` (float, опциональный): Температура генерации (0.0-1.0)

**Заголовки ответа:**

- `X-Agent-ID`: Уникальный идентификатор агента
- `X-Agent-Model`: Используемая модель агента
- `Cache-Control`: no-cache
- `Connection`: keep-alive

**Потоковый ответ:**
Ответ передается как Server-Sent Events (SSE) с обновлениями в реальном времени.

**Пример:**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr-agent",
    "messages": [{"role": "user", "content": "Research AI market trends"}],
    "stream": true,
    "temperature": 0
  }'
```

**Пример с изображением (URL):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr-agent",
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

**Пример с изображением (Base64):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr-agent",
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

</details>

______________________________________________________________________

<details>
<summary><strong>📋 Управление агентами</strong> - Список и мониторинг активных агентов</summary>

## 🔍 GET `/agents`

Получить список всех активных агентов.

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
      "state": "RESEARCHING"
    }
  ],
  "total": 1
}
```

**Состояния агента:**

- `INITED` - Агент инициализирован
- `RESEARCHING` - Агент активно исследует
- `WAITING_FOR_CLARIFICATION` - Агент нуждается в уточнении
- `COMPLETED` - Исследование завершено

**Пример:**

```bash
curl http://localhost:8010/agents
```

</details>

______________________________________________________________________

<details>
<summary><strong>🔍 Состояние агента</strong> - Получить детальную информацию о конкретном агенте</summary>

## 🔍 GET `/agents/{agent_id}/state`

Получить детальную информацию о состоянии конкретного агента.

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
  "state": "RESEARCHING",
  "iteration": 3,
  "searches_used": 2,
  "clarifications_used": 0,
  "sources_count": 5,
  "current_step_reasoning": {
    "action": "web_search",
    "query": "BMW X6 2025 price Russia",
    "reason": "Need current market data"
  }
}
```

**Параметры:**

- `agent_id` (string, обязательный): Уникальный идентификатор агента

**Пример:**

```bash
curl http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/state
```

</details>

______________________________________________________________________

<details>
<summary><strong>❓ Предоставить уточнение</strong> - Ответить на запросы агента на уточнение</summary>

## 🔍 POST `/agents/{agent_id}/provide_clarification`

Предоставить уточнение агенту, который ожидает ввода.

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

**Параметры:**

- `agent_id` (string, обязательный): Уникальный идентификатор агента
- `messages` (array, обязательный): Сообщения уточнения в формате OpenAI (ChatCompletionMessageParam)

**Ответ:**
Потоковый ответ с продолжением исследования после уточнения.

**Пример:**

```bash
curl -X POST "http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}]
  }'
```

</details>

______________________________________________________________________
