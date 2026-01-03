SGR Agent Core provides a comprehensive REST API that is fully compatible with OpenAI's API format, making it easy to integrate with existing applications.

## 🔍 Base URL

```
http://localhost:8010
```

## 🔍 Authentication

No authentication required for local development. For production deployments, configure authentication as needed.

______________________________________________________________________

<details>
<summary><strong>🏥 Health Check</strong> - Check API status and availability</summary>

## 🔍 GET `/health`

Check if the API is running and healthy.

**Response:**

```json
{
  "status": "healthy",
  "service": "sgr-agent-core API"
}
```

**Example:**

```bash
curl http://localhost:8010/health
```

</details>

______________________________________________________________________

<details>
<summary><strong>🤖 Available Models</strong> - Get list of supported agent models</summary>

## 🔍 GET `/v1/models`

Retrieve a list of available agent models.

**Response:**

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

**Available Models:**

- `sgr-agent` - Pure SGR (Schema-Guided Reasoning)
- `sgr-tools-agent` - SGR + Function Calling hybrid
- `sgr-auto-tools-agent` - SGR + Auto Function Calling
- `sgr-so-tools-agent` - SGR + Structured Output
- `tools-agent` - Pure Function Calling

**Example:**

```bash
curl http://localhost:8010/v1/models
```

</details>

______________________________________________________________________

<details>
<summary><strong>💬 Chat Completions</strong> - Main research endpoint with streaming support</summary>

## 🔍 POST `/v1/chat/completions`

Create a chat completion for research tasks. This is the main endpoint for interacting with SGR agents.

**Request Body:**

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

**Parameters:**

- `model` (string, required): Agent type or existing agent ID
- `messages` (array, required): List of chat messages in OpenAI format (ChatCompletionMessageParam)
- `stream` (boolean, default: true): Enable streaming mode
- `max_tokens` (integer, optional): Maximum number of tokens
- `temperature` (float, optional): Generation temperature (0.0-1.0)

**Response Headers:**

- `X-Agent-ID`: Unique agent identifier
- `X-Agent-Model`: Agent model used
- `Cache-Control`: no-cache
- `Connection`: keep-alive

**Streaming Response:**
The response is streamed as Server-Sent Events (SSE) with real-time updates.

**Example:**

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

**Example with Image (URL):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr-agent",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Analyze this chart and research the trends"},
        {"type": "image_url", "image_url": {"url": "https://example.com/chart.png"}}
      ]
    }],
    "stream": true
  }'
```

**Example with Image (Base64):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr-agent",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "What is shown in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."}}
      ]
    }],
    "stream": true
  }'
```

**Note:** Base64 image URLs longer than 200 characters will be truncated in responses for performance reasons.

</details>

______________________________________________________________________

<details>
<summary><strong>📋 Agent Management</strong> - List and monitor active agents</summary>

## 🔍 GET `/agents`

Get a list of all active agents.

**Response:**

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

**Agent States:**

- `INITED` - Agent initialized
- `RESEARCHING` - Agent is actively researching
- `WAITING_FOR_CLARIFICATION` - Agent needs clarification
- `COMPLETED` - Research completed

**Example:**

```bash
curl http://localhost:8010/agents
```

</details>

______________________________________________________________________

<details>
<summary><strong>🔍 Agent State</strong> - Get detailed information about a specific agent</summary>

## 🔍 GET `/agents/{agent_id}/state`

Get detailed state information for a specific agent.

**Response:**

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

**Parameters:**

- `agent_id` (string, required): Unique agent identifier

**Example:**

```bash
curl http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/state
```

</details>

______________________________________________________________________

<details>
<summary><strong>❓ Provide Clarification</strong> - Respond to agent clarification requests</summary>

## 🔍 POST `/agents/{agent_id}/provide_clarification`

Provide clarification to an agent that is waiting for input.

**Request Body:**

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

**Parameters:**

- `agent_id` (string, required): Unique agent identifier
- `messages` (array, required): Clarification messages in OpenAI format (ChatCompletionMessageParam)

**Response:**
Streaming response with continued research after clarification.

**Example:**

```bash
curl -X POST "http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}]
  }'
```

</details>

______________________________________________________________________
