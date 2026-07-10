# Интеграция с Langfuse

[Langfuse](https://langfuse.com) — open-source платформа для наблюдаемости LLM-приложений.
При включении SGR Agent Core оборачивает OpenAI-клиент трассировкой Langfuse — каждый вызов
LLM автоматически записывается как трейс с входными данными, ответом, латентностью и
количеством токенов.

## Быстрый старт

Добавьте блок `langfuse` в ваш `config.yaml`:

```yaml
langfuse:
  enabled: true
  public_key: "pk-lf-..."
  secret_key: "sk-lf-..."
  host: "https://cloud.langfuse.com"  # или ваш self-hosted URL
```

Готово. При следующем запуске агента трейсы появятся в интерфейсе Langfuse.

---

## Сценарии подключения

### Вариант 1: Langfuse Cloud

Самый простой вариант — использовать облачный сервис [cloud.langfuse.com](https://cloud.langfuse.com).

1. Зарегистрируйтесь на [cloud.langfuse.com](https://cloud.langfuse.com) и создайте проект.
2. Скопируйте **Public Key** и **Secret Key** из *Project Settings → API Keys*.
3. Добавьте в `config.yaml`:

```yaml
langfuse:
  enabled: true
  public_key: "pk-lf-..."
  secret_key: "sk-lf-..."
  host: "https://cloud.langfuse.com"
```

!!! note
    По умолчанию Langfuse SDK использует `https://cloud.langfuse.com`, поэтому для облачного
    варианта `host` можно опустить. Здесь он указан явно для наглядности.

---

### Вариант 2: Self-Hosted Langfuse

Запустите Langfuse на собственной инфраструктуре с помощью официального Docker Compose.

1. Следуйте [инструкции по self-hosting](https://langfuse.com/docs/deployment/self-host)
   для запуска Langfuse локально:

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up -d
```

По умолчанию Langfuse будет доступен по адресу `http://localhost:3000`.

2. Откройте `http://localhost:3000`, создайте проект и скопируйте API-ключи.

3. Укажите адрес вашего инстанса в SGR:

```yaml
langfuse:
  enabled: true
  public_key: "pk-lf-..."
  secret_key: "sk-lf-..."
  host: "http://localhost:3000"
```

!!! tip
    Для production-развёртываний замените `localhost` на hostname или IP вашего сервера Langfuse
    (например, `https://langfuse.internal.example.com`).

---

### Вариант 3: Через LiteLLM Proxy

[LiteLLM](https://docs.litellm.ai/) может выступать единым прокси перед несколькими LLM-провайдерами
и автоматически форвардить трейсы в Langfuse.

**Поток запросов:**

```
SGR Agent → LiteLLM Proxy → LLM-провайдер (OpenAI и др.)
                ↓
            Langfuse
```

1. Настройте LiteLLM для передачи трейсов в Langfuse.
   В `config.yaml` LiteLLM добавьте callback:

```yaml
# litellm/config.yaml
litellm_settings:
  success_callback: ["langfuse"]

environment_variables:
  LANGFUSE_PUBLIC_KEY: "pk-lf-..."
  LANGFUSE_SECRET_KEY: "sk-lf-..."
  LANGFUSE_HOST: "https://cloud.langfuse.com"
```

2. В `config.yaml` SGR укажите base URL на ваш LiteLLM-прокси и **отключите** интеграцию
   Langfuse на уровне SGR (трассировкой занимается LiteLLM):

```yaml
llm:
  api_key: "your-litellm-api-key"
  base_url: "http://localhost:4000"  # адрес LiteLLM proxy
  model: "gpt-4o"

langfuse:
  enabled: false  # LiteLLM берёт трассировку на себя
```

!!! note
    При желании можно включить Langfuse и в SGR, и в LiteLLM одновременно — вы получите
    два уровня трейсов (LLM-вызовы на стороне SGR + маршрутизация на стороне LiteLLM).
    В большинстве случаев достаточно одного уровня.

---

## Переменные окружения

Все параметры блока `langfuse` можно задать через переменные окружения с префиксом `SGR__LANGFUSE__`:

```bash
SGR__LANGFUSE__ENABLED=true
SGR__LANGFUSE__PUBLIC_KEY=pk-lf-xxx
SGR__LANGFUSE__SECRET_KEY=sk-lf-xxx
SGR__LANGFUSE__HOST=http://localhost:3000
```

Если ключи уже заданы в нативных переменных Langfuse, используйте сокращённую форму — без
дублирования ключей:

```bash
# Эти переменные читаются непосредственно Langfuse SDK
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=http://localhost:3000
```

```yaml
# config.yaml — сокращённая форма, ключи из LANGFUSE_* env
langfuse: true
```

!!! warning "Загрузка `.env`-файлов"
    Python **не** загружает `.env` автоматически.
    Сервер SGR (CLI `sgr`) загружает `.env` при старте через `python-dotenv`.
    Если вы используете SGR как библиотеку, вызовите `load_dotenv()` самостоятельно
    до инициализации `GlobalConfig`.

---

## Решение проблем

### `LangfuseImportError` / не удаётся импортировать `langfuse`

Если в конфигурации `langfuse.enabled: true`, но пакет `langfuse` не установлен или недоступен
для импорта, при старте агента выбрасывается `LangfuseImportError` с понятным текстом.
Установите зависимости проекта (`langfuse` входит в основные зависимости SGR Agent Core) либо
отключите Langfuse, установив `langfuse.enabled` в `false`.

### "Authentication error: Langfuse client initialized without public_key"

Langfuse SDK не может найти ключи. Проверьте следующее:

- `public_key` и `secret_key` указаны в `config.yaml` в блоке `langfuse:`, **либо**
  `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` присутствуют в окружении.
- Если используете `.env`, убедитесь что сервер запущен через CLI `sgr` (он загружает `.env`),
  а не напрямую как Python-модуль.
