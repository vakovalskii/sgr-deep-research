# Установка

SGR Agent Core можно установить через pip или Docker. Выберите метод, который лучше всего подходит для ваших нужд.

## Установка через pip

### Базовая установка

Установите основной пакет:

```bash
pip install sgr-agent-core
```

### Установка с дополнительными зависимостями

Для разработки можно установить с дополнительными зависимостями:

```bash
# Установка с зависимостями для разработки
pip install sgr-agent-core[dev]

# Установка с зависимостями для тестирования
pip install sgr-agent-core[tests]

# Установка с зависимостями для документации
pip install sgr-agent-core[docs]
```

### Требования

* Python 3.11 или выше
* API ключ для LLM, совместимого с OpenAI (или эндпоинт локальной модели)

### Проверка установки

После установки проверьте, что пакет установлен правильно:

```bash
python -c "import sgr_agent_core; print(sgr_agent_core.__version__)"
```

Также вы должны иметь возможность использовать утилиты командной строки:

```bash
# Команда API сервера
sgr --help
# или с коротким параметром
sgr -c config.yaml

# Интерактивная CLI команда
sgrsh --help
sgrsh "Ваш запрос здесь"
```

## Установка через Docker

### Использование Docker образа

Загрузите официальный Docker образ:

```bash
docker pull ghcr.io/vamplabai/sgr-agent-core:latest
```

### Запуск с Docker

Запустите контейнер с вашей конфигурацией:

```bash
docker run -d \
  --name sgr-agent \
  -p 8010:8010 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/agents.yaml:/app/agents.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  -e SGR__LLM__API_KEY=your-api-key \
  ghcr.io/vamplabai/sgr-agent-core:latest \
  --config-file /app/config.yaml \
  --host 0.0.0.0 \
  --port 8010
```

### Использование Docker Compose

Для полной настройки с фронтендом используйте Docker Compose:

1. Скопируйте пример файла docker-compose:

```bash
cp docker-compose.dist.yaml docker-compose.yaml
```

2. Отредактируйте `docker-compose.yaml` и настройте параметры:

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    command:
      - --config-file=/app/config.yaml
      - --agents-file=/app/agents.yaml
    ports:
      - "8010:8010"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./agents.yaml:/app/agents.yaml:ro
      - ./logs:/app/logs
      - ./reports:/app/reports
    environment:
      - SGR__LLM__API_KEY=your-api-key
      - SGR__LLM__BASE_URL=https://api.openai.com/v1
```

3. Запустите сервисы:

```bash
docker-compose up -d
```

API сервер будет доступен по адресу `http://localhost:8010`. Интерактивная документация API (Swagger UI) доступна по адресу `http://localhost:8010/docs`.

### Сборка из исходников

Если вы хотите собрать Docker образ из исходников:

```bash
git clone https://github.com/vamplabAI/sgr-agent-core.git
cd sgr-agent-core
docker build -t sgr-agent-core:latest .
```

## Конфигурация

После установки вам нужно настроить API ключи и параметры. См. [Руководство по конфигурации](../framework/configuration.md) для подробных инструкций.

### Быстрая конфигурация

Создайте файл `config.yaml`:

```yaml
llm:
  api_key: "your-api-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

execution:
  max_iterations: 7
  max_clarifications: 3
```

Или используйте переменные окружения:

```bash
export SGR__LLM__API_KEY="your-api-key"
export SGR__LLM__BASE_URL="https://api.openai.com/v1"
export SGR__LLM__MODEL="gpt-4o"
```

## Следующие шаги

* **[Руководство по быстрому старту](../framework/first-steps.md)** — Начните работу с вашим первым агентом
* **[Руководство по конфигурации](../framework/configuration.md)** — Настройте ваших агентов
