## 🚀 <strong>Примеры Python OpenAI Client</strong> - Полное руководство по интеграции с потоковой передачей и уточнениями</summary>

Простые примеры Python для использования клиента OpenAI с системой SGR Agent Core.

### Требования

```bash
pip install openai
```

### Пример 1: Базовый исследовательский запрос

Простой исследовательский запрос без уточнений.

```python
from openai import OpenAI

# Инициализация клиента
client = OpenAI(
    base_url="http://localhost:8010/v1",
    api_key="dummy",  # Не требуется для локального сервера
)

# Выполнить исследовательский запрос
response = client.chat.completions.create(
    model="sgr-agent",
    messages=[{"role": "user", "content": "Research BMW X6 2025 prices in Russia"}],
    stream=True,
    temperature=0.4,
)

# Вывести потоковый ответ
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Пример 2: Исследование с поддержкой уточнений

Обработка запросов агента на уточнение и продолжение разговора.

```python
import json
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8010/v1", api_key="dummy")

# Шаг 1: Начальный исследовательский запрос
print("Начало исследования...")
response = client.chat.completions.create(
    model="sgr-agent",
    messages=[{"role": "user", "content": "Research AI market trends"}],
    stream=True,
    temperature=0,
)

agent_id = None
clarification_questions = []

# Обработка потокового ответа
for chunk in response:
    # Извлечь ID агента из поля model
    if chunk.model and chunk.model.startswith("sgr_agent_"):
        agent_id = chunk.model
        print(f"\nID агента: {agent_id}")

    # Проверить запросы на уточнение
    if chunk.choices[0].delta.tool_calls:
        for tool_call in chunk.choices[0].delta.tool_calls:
            if tool_call.function and tool_call.function.name == "clarification":
                args = json.loads(tool_call.function.arguments)
                clarification_questions = args.get("questions", [])

    # Вывести содержимое
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# Шаг 2: Обработать уточнение, если необходимо
if clarification_questions and agent_id:
    print(f"\n\nТребуется уточнение:")
    for i, question in enumerate(clarification_questions, 1):
        print(f"{i}. {question}")

    # Предоставить уточнение
    clarification = "Focus on LLM market trends for 2024-2025, global perspective"
    print(f"\nПредоставление уточнения: {clarification}")

    # Продолжить с ID агента
    response = client.chat.completions.create(
        model=agent_id,  # Использовать ID агента как модель
        messages=[{"role": "user", "content": clarification}],
        stream=True,
        temperature=0,
    )

    # Вывести финальный ответ
    for chunk in response:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")

print("\n\nИсследование завершено!")
```

### Пример 3: Исследовательский запрос с изображением

Отправка исследовательского запроса с локальным файлом изображения.

```python
import base64
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8010/v1", api_key="dummy")

# Прочитать локальный файл изображения и закодировать в base64
with open("chart.png", "rb") as image_file:
    image_data = base64.b64encode(image_file.read()).decode("utf-8")
    image_url = f"data:image/png;base64,{image_data}"

# Исследовательский запрос с локальным изображением
response = client.chat.completions.create(
    model="sgr-agent",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Проанализируй этот график и исследуй показанные тренды"},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    }],
    stream=True,
    temperature=0.4,
)

# Вывести потоковый ответ
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

**Поддерживаемые форматы изображений:**
- Локальные файлы изображений (конвертируются в Base64): PNG, JPEG, GIF, WebP
- URL изображений (HTTP/HTTPS)
- Изображения в формате Base64 (`data:image/jpeg;base64,...` или `data:image/png;base64,...`)

#### Примечания по использованию

- Замените `localhost:8010` на URL вашего сервера
- `api_key` может быть любой строкой для локального сервера
- ID агента возвращается в поле `model` во время потоковой передачи
- Вопросы уточнения отправляются через `tool_calls` с именем функции `clarification`
- Используйте ID агента как имя модели для продолжения разговора

______________________________________________________________________

## <summary>⚡ <strong>Примеры cURL API</strong> - Прямые HTTP запросы с прерыванием агента и потоком уточнений</summary>

Система предоставляет полностью совместимый с OpenAI API с расширенными возможностями прерывания агента и уточнений.

### Базовый исследовательский запрос

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
    "messages": [{"role": "user", "content": "Research BMW X6 2025 prices in Russia"}],
    "stream": true,
    "max_tokens": 1500,
    "temperature": 0.4
  }'
```

### Поток прерывания агента и уточнений

Когда агенту требуется уточнение, он возвращает уникальный ID агента в поле model потокового ответа. Затем вы можете продолжить разговор, используя этот ID агента.

#### Шаг 1: Начальный запрос

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
    "messages": [{"role": "user", "content": "Research AI market trends"}],
    "stream": true,
    "max_tokens": 1500,
    "temperature": 0
  }'
```

#### Шаг 2: Агент запрашивает уточнение

Потоковый ответ включает ID агента в поле model:

```json
{
  "model": "sgr_agent_b84d5a01-c394-4499-97be-dad6a5d2cb86",
  "choices": [{
    "delta": {
      "tool_calls": [{
        "function": {
          "name": "clarification",
          "arguments": "{\"questions\":[\"Which specific AI market segment are you interested in (LLM, computer vision, robotics)?\", \"What time period should I focus on (2024, next 5 years)?\", \"Are you looking for global trends or specific geographic regions?\", \"Do you need technical analysis or business/investment perspective?\"]}"
        }
      }]
    }
  }]
}
```

#### Шаг 3: Продолжить с ID агента

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent_b84d5a01-c394-4499-97be-dad6a5d2cb86",
    "messages": [{"role": "user", "content": "Focus on LLM market trends for 2024-2025, global perspective, business analysis"}],
    "stream": true,
    "max_tokens": 1500,
    "temperature": 0
  }'
```

### Управление агентами

```bash
# Получить всех активных агентов
curl http://localhost:8010/agents

# Получить состояние конкретного агента
curl http://localhost:8010/agents/{agent_id}/state

# Прямой endpoint уточнения
curl -X POST "http://localhost:8010/agents/{agent_id}/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}],
    "stream": true
  }'
```
