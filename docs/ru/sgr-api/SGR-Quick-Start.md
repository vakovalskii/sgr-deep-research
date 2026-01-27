Это руководство поможет вам быстро начать работу с запуском SGR Agent Core как REST API сервиса.

## Настройка файлов конфигурации

1. **Создайте config.yaml из шаблона:**

```bash
cp config.yaml.example config.yaml
```

> Альтернативно, вы можете использовать переменные окружения из .env.example

2. **Настройте API ключи и другие параметры**

3. (опционально) **Заполните свои определения агентов:**

```bash
touch agents.yaml
# Добавьте в этот файл определения ваших агентов на основе config.yaml и agents.yaml.example
```

## Локальная разработка

### Требования

#### Установка UV (для Backend)

UV требуется для управления зависимостями Python и запуска backend.

```bash
# Установка UV
curl -LsSf https://astral.sh/uv/install.sh | sh
# или на Windows:
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Установка Node.js и npm (для Frontend)

Node.js и npm требуются для запуска frontend сервера разработки.

```bash
# Проверьте, установлен ли Node.js
node --version
npm --version

# Если не установлен, скачайте с https://nodejs.org/
# Или используйте менеджер версий, например nvm:
# nvm install 22
# nvm use 22
```

**Требования:**

- Node.js: `^20.19.0 || >=22.12.0` (см. поле engines в `package.json`)

### Запуск Backend

```bash
# 1. Установите зависимости
uv sync

# 2. Запустите сервер с настройками по умолчанию
uv run python sgr_agent_core

# Или с пользовательскими опциями:
uv run python sgr_agent_core \
  --host 127.0.0.1 \
  --port 8010 \
  --config-file config.yaml \
  --agents-file agents.yaml \
  --logging-file logging_config.yaml
```

### Запуск Frontend

```bash
# 1. Перейдите в директорию frontend
cd sgr-deep-research-frontend

# 2. Установите зависимости
npm install

# 3. Запустите сервер разработки с настройками по умолчанию
npm run dev

# Или с пользовательским URL backend:
VITE_API_BASE_URL=http://localhost:8010 npm run dev

**Примечание:** В режиме разработки Vite автоматически проксирует API запросы (`/health`, `/agents`, `/v1/*`) к backend, поэтому обычно вам не нужно устанавливать `VITE_API_BASE_URL`, если только ваш backend не работает на другом хосте/порту.
```

### URL для доступа (Локальная разработка)

После запуска backend и frontend, вы можете получить доступ:

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8010
  - **Документация API (Swagger UI):** http://localhost:8010/docs
  - Проверка здоровья: http://localhost:8010/health
  - Endpoint агентов: http://localhost:8010/agents
  - API endpoints: http://localhost:8010/v1/\*

## Развертывание Docker

### Использование готового Docker-образа

Проект предоставляет готовые Docker-образы, опубликованные в GitHub Container Registry (ghcr.io). Вы можете использовать эти образы напрямую без сборки из исходного кода.

#### Загрузка и запуск образа

```bash
# Загрузить последний образ
docker pull ghcr.io/vamplabai/sgr-agent-core:latest

# Запустить контейнер
docker run -d \
  --name sgr-agent-backend \
  -p 8010:8010 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/agents.yaml:/app/agents.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  ghcr.io/vamplabai/sgr-agent-core:latest
```

#### Использование конкретной версии

Вы также можете использовать конкретную версию:

```bash
# Загрузить конкретную версию
docker pull ghcr.io/vamplabai/sgr-agent-core:v1.0.0

# Запустить с конкретной версией
docker run -d \
  --name sgr-agent-backend \
  -p 8010:8010 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/agents.yaml:/app/agents.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  ghcr.io/vamplabai/sgr-agent-core:v1.0.0
```

#### Пользовательская конфигурация

Вы можете переопределить путь к файлу конфигурации по умолчанию:

```bash
docker run -d \
  --name sgr-agent-backend \
  -p 8010:8010 \
  -e CONFIG_FILE=/app/config.yaml \
  -v $(pwd)/my-config.yaml:/app/config.yaml:ro \
  -v $(pwd)/my-agents.yaml:/app/agents.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  ghcr.io/vamplabai/sgr-agent-core:latest \
  --config-file /app/config.yaml \
  --agents-file /app/agents.yaml
```

#### URL для доступа (Готовый образ)

После запуска контейнера вы можете получить доступ:

- **Backend API:** http://localhost:8010
  - **Документация API (Swagger UI):** http://localhost:8010/docs
  - Проверка здоровья: http://localhost:8010/health
  - Endpoint агентов: http://localhost:8010/agents
  - API endpoints: http://localhost:8010/v1/\*

### Сборка из исходного кода

Если вам нужно собрать Docker-образ из исходного кода, вы можете использовать Docker Compose.

#### Переменные окружения

Перед развертыванием вы можете настроить следующие переменные окружения (опционально):

- `VITE_API_BASE_URL` - Базовый URL для backend API (по умолчанию: `http://localhost:8010`)
- `VITE_APP_ENV` - Окружение приложения (по умолчанию: `production`)
- `FRONTEND_PORT` - Порт для frontend сервиса (по умолчанию: `5173`)
- `BACKEND_PORT` - Порт для backend сервиса (по умолчанию: `8010`)

#### Шаги развертывания

```bash
# 1. Скопируйте docker-compose.dist.yaml в docker-compose.yaml
cp docker-compose.dist.yaml docker-compose.yaml

# 2. Сборка docker образов
docker-compose build

# 3. Развертывание с Docker Compose
docker-compose up -d
```

#### URL для доступа (Docker Compose)

После развертывания вы можете получить доступ:

- **Frontend:** http://localhost:5173 (или пользовательский `FRONTEND_PORT`)
- **Backend API:** http://localhost:8010 (или пользовательский `BACKEND_PORT`)
  - **Документация API (Swagger UI):** http://localhost:8010/docs
  - Проверка здоровья: http://localhost:8010/health
  - Endpoint агентов: http://localhost:8010/agents
  - API endpoints: http://localhost:8010/v1/\*
