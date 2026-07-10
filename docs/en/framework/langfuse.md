# Langfuse Integration

[Langfuse](https://langfuse.com) is an open-source observability platform for LLM applications.
When enabled, SGR Agent Core wraps the OpenAI client with Langfuse tracing — every LLM call
is automatically recorded as a trace with inputs, outputs, latency, and token usage.

## Quick Start

Add the `langfuse` block to your `config.yaml`:

```yaml
langfuse:
  enabled: true
  public_key: "pk-lf-..."
  secret_key: "sk-lf-..."
  host: "https://cloud.langfuse.com"  # or your self-hosted URL
```

That's it. On the next agent run you will see traces appearing in the Langfuse UI.

---

## Connection Scenarios

### Option 1: Langfuse Cloud

The simplest option — use the managed service at [cloud.langfuse.com](https://cloud.langfuse.com).

1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com) and create a project.
2. Copy **Public Key** and **Secret Key** from *Project Settings → API Keys*.
3. Add to `config.yaml`:

```yaml
langfuse:
  enabled: true
  public_key: "pk-lf-..."
  secret_key: "sk-lf-..."
  host: "https://cloud.langfuse.com"
```

!!! note
    `host` defaults to `https://cloud.langfuse.com` in the Langfuse SDK, so you can omit it
    for the cloud deployment. It is shown here explicitly for clarity.

---

### Option 2: Self-Hosted Langfuse

Run Langfuse on your own infrastructure using the official Docker Compose setup.

1. Follow the [self-hosting guide](https://langfuse.com/docs/deployment/self-host) to start Langfuse locally:

```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up -d
```

Langfuse will be available at `http://localhost:3000` by default.

2. Open `http://localhost:3000`, create a project, and copy the API keys.

3. Point SGR at your instance:

```yaml
langfuse:
  enabled: true
  public_key: "pk-lf-..."
  secret_key: "sk-lf-..."
  host: "http://localhost:3000"
```

!!! tip
    For production deployments, replace `localhost` with the hostname or IP of your Langfuse server
    (e.g. `https://langfuse.internal.example.com`).

---

### Option 3: Via LiteLLM Proxy

[LiteLLM](https://docs.litellm.ai/) can act as a unified proxy in front of multiple LLM providers
and forward traces to Langfuse automatically.

**Request flow:**

```
SGR Agent → LiteLLM Proxy → LLM Provider (OpenAI, etc.)
                ↓
            Langfuse
```

1. Configure LiteLLM to forward traces to Langfuse.
   In your LiteLLM `config.yaml`, add the Langfuse callback:

```yaml
# litellm/config.yaml
litellm_settings:
  success_callback: ["langfuse"]

environment_variables:
  LANGFUSE_PUBLIC_KEY: "pk-lf-..."
  LANGFUSE_SECRET_KEY: "sk-lf-..."
  LANGFUSE_HOST: "https://cloud.langfuse.com"
```

2. In SGR's `config.yaml`, point the LLM base URL at your LiteLLM proxy and **disable** the
   SGR-level Langfuse integration (LiteLLM handles tracing itself):

```yaml
llm:
  api_key: "your-litellm-api-key"
  base_url: "http://localhost:4000"  # LiteLLM proxy address
  model: "gpt-4o"

langfuse:
  enabled: false  # LiteLLM handles tracing
```

!!! note
    Alternatively, you can enable Langfuse in SGR **and** in LiteLLM at the same time —
    you will get two levels of tracing (SGR-side LLM calls + LiteLLM-side routing).
    In most cases, one level is sufficient.

---

## Environment Variables

All `langfuse` config fields can be set via environment variables using the `SGR__LANGFUSE__*`
prefix:

```bash
SGR__LANGFUSE__ENABLED=true
SGR__LANGFUSE__PUBLIC_KEY=pk-lf-xxx
SGR__LANGFUSE__SECRET_KEY=sk-lf-xxx
SGR__LANGFUSE__HOST=http://localhost:3000
```

Alternatively, when credentials are already in native Langfuse environment variables, use the
shorthand to enable SGR integration without duplicating credentials:

```bash
# These are read directly by the Langfuse SDK
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=http://localhost:3000
```

```yaml
# config.yaml — shorthand, credentials come from LANGFUSE_* env vars
langfuse: true
```

!!! warning "Loading `.env` files"
    Environment variables in `.env` are **not** loaded automatically by Python.
    SGR's server (`sgr` CLI) loads `.env` on startup via `python-dotenv`.
    If you run SGR as a library, call `load_dotenv()` yourself before initializing `GlobalConfig`.

---

## Troubleshooting

### `LangfuseImportError` / cannot import `langfuse`

If `langfuse.enabled` is `true` in configuration but the `langfuse` package is not installed
or cannot be imported, agent startup raises `LangfuseImportError` with a clear message.
Install the project dependencies (`langfuse` is a core dependency of SGR Agent Core) or
disable Langfuse by setting `langfuse.enabled` to `false`.

### "Authentication error: Langfuse client initialized without public_key"

The Langfuse SDK cannot find credentials. Check the following:

- `public_key` and `secret_key` are set in `config.yaml` under `langfuse:`, **or**
  `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are present in the environment.
- If using `.env`, make sure the server was started via the `sgr` CLI (which loads `.env`)
  rather than called directly as a Python module.
