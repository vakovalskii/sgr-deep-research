# Installation

SGR Agent Core can be installed via pip or Docker. Choose the method that best fits your needs.

## Installation via pip

### Basic Installation

Install the core package:

```bash
pip install sgr-agent-core
```

### Installation with Optional Dependencies

For development, you can install with additional dependencies:

```bash
# Install with development dependencies
pip install sgr-agent-core[dev]

# Install with test dependencies
pip install sgr-agent-core[tests]

# Install with documentation dependencies
pip install sgr-agent-core[docs]
```

### Requirements

* Python 3.11 or higher
* OpenAI-compatible LLM API key (or local model endpoint)

### Verify Installation

After installation, verify that the package is correctly installed:

```bash
python -c "import sgr_agent_core; print(sgr_agent_core.__version__)"
```

You should also be able to use the command-line utilities:

```bash
# API server command
sgr --help
# or with short option
sgr -c config.yaml

# Interactive CLI command
sgrsh --help
sgrsh "Your query here"
```

## Installation via Docker

### Using Docker Image

Pull the official Docker image:

```bash
docker pull ghcr.io/vamplabai/sgr-agent-core:latest
```

### Running with Docker

Run the container with your configuration:

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

### Using Docker Compose

For a complete setup with frontend, use Docker Compose:

1. Copy the example docker-compose file:

```bash
cp docker-compose.dist.yaml docker-compose.yaml
```

2. Edit `docker-compose.yaml` and configure your settings:

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

3. Start the services:

```bash
docker-compose up -d
```

The API server will be available at `http://localhost:8010`. Interactive API documentation (Swagger UI) is available at `http://localhost:8010/docs`.

### Building from Source

If you want to build the Docker image from source:

```bash
git clone https://github.com/vamplabAI/sgr-agent-core.git
cd sgr-agent-core
docker build -t sgr-agent-core:latest .
```

## Configuration

After installation, you'll need to configure your API keys and settings. See the [Configuration Guide](../framework/configuration.md) for detailed instructions.

### Quick Configuration

Create a `config.yaml` file:

```yaml
llm:
  api_key: "your-api-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

execution:
  max_iterations: 7
  max_clarifications: 3
```

Or use environment variables:

```bash
export SGR__LLM__API_KEY="your-api-key"
export SGR__LLM__BASE_URL="https://api.openai.com/v1"
export SGR__LLM__MODEL="gpt-4o"
```

## Next Steps

* **[Quick Start Guide](../framework/first-steps.md)** — Get started with your first agent
* **[Configuration Guide](../framework/configuration.md)** — Configure your agents
