This guide will help you quickly get started with running SGR Agent Core as a REST API service.

## Setup Configuration Files

1. **Create config.yaml from the template:**

```bash
cp config.yaml.example config.yaml
```

> Alternatively, you can use environment variables from .env.example

2. **Configure API keys and other settings**

3. (optional) **Fill in your own agents definitions:**

```bash
touch agents.yaml
# Add in this file your agents definitions based on config.yaml and agents.yaml.example
```

## Local Development

### Prerequisites

#### Install UV (for Backend)

UV is required for managing Python dependencies and running the backend.

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
# or on Windows:
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Install Node.js and npm (for Frontend)

Node.js and npm are required for running the frontend development server.

```bash
# Check if Node.js is installed
node --version
npm --version

# If not installed, download from https://nodejs.org/
# Or use a version manager like nvm:
# nvm install 22
# nvm use 22
```

**Requirements:**

- Node.js: `^20.19.0 || >=22.12.0` (see `package.json` engines field)

### Backend Run

```bash
# 1. Install dependencies
uv sync

# 2. Run the server with default settings
uv run python sgr_agent_core

# Or with custom options:
uv run python sgr_agent_core \
  --host 127.0.0.1 \
  --port 8010 \
  --config-file config.yaml \
  --agents-file agents.yaml \
  --logging-file logging_config.yaml
```

### Frontend Run

```bash
# 1. Navigate to frontend directory
cd sgr-deep-research-frontend

# 2. Install dependencies
npm install

# 3. Run the development server with default settings
npm run dev

# Or with custom backend URL:
VITE_API_BASE_URL=http://localhost:8010 npm run dev

**Note:** In development mode, Vite automatically proxies API requests (`/health`, `/agents`, `/v1/*`) to the backend, so you typically don't need to set `VITE_API_BASE_URL` unless your backend is running on a different host/port.
```

### Access URLs (Local Development)

After starting both backend and frontend, you can access:

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8010
  - **API Documentation (Swagger UI):** http://localhost:8010/docs
  - Health check: http://localhost:8010/health
  - Agents endpoint: http://localhost:8010/agents
  - API endpoints: http://localhost:8010/v1/\*

## Docker Deployment

### Using Pre-built Docker Image

The project provides pre-built Docker images published to GitHub Container Registry (ghcr.io). You can use these images directly without building from source.

#### Pull and Run the Image

```bash
# Pull the latest image
docker pull ghcr.io/vamplabai/sgr-agent-core:latest

# Run the container
docker run -d \
  --name sgr-agent-backend \
  -p 8010:8010 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/agents.yaml:/app/agents.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  ghcr.io/vamplabai/sgr-agent-core:latest
```

#### Using Specific Version

You can also use a specific version tag:

```bash
# Pull a specific version
docker pull ghcr.io/vamplabai/sgr-agent-core:v1.0.0

# Run with specific version
docker run -d \
  --name sgr-agent-backend \
  -p 8010:8010 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/agents.yaml:/app/agents.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/reports:/app/reports \
  ghcr.io/vamplabai/sgr-agent-core:v1.0.0
```

#### Custom Configuration

You can override the default configuration file path:

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

#### Access URLs (Pre-built Image)

After starting the container, you can access:

- **Backend API:** http://localhost:8010
  - **API Documentation (Swagger UI):** http://localhost:8010/docs
  - Health check: http://localhost:8010/health
  - Agents endpoint: http://localhost:8010/agents
  - API endpoints: http://localhost:8010/v1/\*

### Building from Source

If you need to build the Docker image from source, you can use Docker Compose.

#### Environment Variables

Before deploying, you can configure the following environment variables (optional):

- `VITE_API_BASE_URL` - Base URL for the backend API (default: `http://localhost:8010`)
- `VITE_APP_ENV` - Application environment (default: `production`)
- `FRONTEND_PORT` - Port for the frontend service (default: `5173`)
- `BACKEND_PORT` - Port for the backend service (default: `8010`)

#### Deployment Steps

```bash
# 1. Copy docker-compose.dist.yaml to docker-compose.yaml
cp docker-compose.dist.yaml docker-compose.yaml

# 2. Building docker images
docker-compose build

# 3. Deploy with Docker Compose
docker-compose up -d
```

#### Access URLs (Docker Compose)

After deployment, you can access:

- **Frontend:** http://localhost:5173 (or custom `FRONTEND_PORT`)
- **Backend API:** http://localhost:8010 (or custom `BACKEND_PORT`)
  - **API Documentation (Swagger UI):** http://localhost:8010/docs
  - Health check: http://localhost:8010/health
  - Agents endpoint: http://localhost:8010/agents
  - API endpoints: http://localhost:8010/v1/\*
