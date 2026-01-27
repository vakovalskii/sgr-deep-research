SGR Agent Core provides a comprehensive REST API that is fully compatible with OpenAI's API format, making it easy to integrate with existing applications.

## Base URL

```
http://localhost:8010
```

## API Documentation

Interactive API documentation (Swagger UI) is available at `http://localhost:8010/docs`. You can explore all endpoints, test requests, and view request/response schemas directly in your browser.

## Authentication

Authentication is not supported by the API. For production deployments, use a reverse proxy with authentication configured.

## GET `/health`

Check if the API is running and healthy.

**Request:**

```bash
curl http://localhost:8010/health
```

**Response:**

```json
{
  "status": "healthy",
  "service": "SGR Agent Core API"
}
```

**Response Fields:**

- `status` (string, literal: "healthy"): Always returns "healthy" when API is operational
- `service` (string): Service name identifier

## GET `/v1/models`

Retrieve a list of available agent models. This endpoint returns all agent definitions configured in the system.

**Available Models:**

- `sgr_agent` - Pure SGR (Schema-Guided Reasoning)
- `sgr_tool_calling_agent` - SGR + Function Calling hybrid
- `tool_calling_agent` - Pure Function Calling

**Request:**

```bash
curl http://localhost:8010/v1/models
```

**Response:**

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

**Response Fields:**

- `data` (array): List of available agent models
  - `id` (string): Agent model identifier (matches agent definition name)
  - `object` (string, literal: "model"): Object type identifier
  - `created` (integer): Timestamp placeholder (OpenAI compatibility)
  - `owned_by` (string): Always "sgr-agent-core"
- `object` (string, literal: "list"): Response type identifier

## POST `/v1/chat/completions`

Create a chat completion for research tasks. This is the main endpoint for interacting with SGR agents. Creates a new agent instance and starts its execution asynchronously.

**Request Body:**

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

**Request Parameters:**

- `model` (string, required, default: "sgr_tool_calling_agent"): Agent type name (e.g., "sgr_agent", "sgr_tool_calling_agent") or existing agent ID for clarification requests
- `messages` (array, required): List of chat messages in OpenAI format (ChatCompletionMessageParam). Supports:
  - Text messages: `{"role": "user", "content": "text"}`
  - Multimodal messages: `{"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}}]}`
  - System messages: `{"role": "system", "content": "..."}`
- `stream` (boolean, required, default: true): **Must be `true`** - only streaming responses are supported
- `max_tokens` (integer, optional, default: 1500): Maximum number of tokens for generation
- `temperature` (float, optional, default: 0): Generation temperature (0.0-1.0). Lower values make output more deterministic

**Special Behavior - Clarification Requests:**

If `model` contains an agent ID (format: `{agent_name}_{uuid}`) and the agent is in `waiting_for_clarification` state, this endpoint will automatically route to the clarification handler instead of creating a new agent.

**Response:**

**Response Headers:**

- `X-Agent-ID` (string): Unique agent identifier (format: `{agent_name}_{uuid}`)
- `X-Agent-Model` (string): Agent model name used
- `Cache-Control`: `no-cache`
- `Connection`: `keep-alive`
- `Content-Type`: `text/event-stream`

**Streaming Response Format:**

The response is streamed as Server-Sent Events (SSE) with real-time updates. Each event follows OpenAI-compatible format:

```
data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"sgr_agent","choices":[{"index":0,"delta":{"content":"..."},"finish_reason":null}]}

data: {"id":"...","object":"chat.completion.chunk","created":...,"model":"sgr_agent","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Error Responses:**

- `400 Bad Request`: Invalid model name or malformed request
  ```json
  {
    "detail": "Invalid model 'invalid_model'. Available models: ['sgr_agent', 'sgr_tool_calling_agent']"
  }
  ```
- `501 Not Implemented`: Non-streaming request (stream must be true)
  ```json
  {
    "detail": "Only streaming responses are supported. Set 'stream=true'"
  }
  ```

**Request:**

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

**Request with Image (URL):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
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

**Request with Image (Base64):**

```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sgr_agent",
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

## GET `/agents`

Get a list of all active agents currently stored in memory. Returns empty list if no agents are active.

**Request:**

```bash
curl http://localhost:8010/agents
```

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
      "state": "researching",
      "creation_time": "2025-01-27T12:00:00"
    }
  ],
  "total": 1
}
```

**Response Fields:**

- `agents` (array): List of agent items
  - `agent_id` (string): Unique agent identifier (format: `{agent_name}_{uuid}`)
  - `task_messages` (array): Original task messages in OpenAI format
  - `state` (string): Current agent state (see Agent States below)
  - `creation_time` (string, ISO 8601): Agent creation timestamp
- `total` (integer): Total number of agents in storage

**Agent States:**

- `inited` - Agent initialized, ready to start
- `researching` - Agent is actively researching and executing tasks
- `waiting_for_clarification` - Agent needs user clarification to proceed
- `completed` - Research completed successfully
- `cancelled` - Agent execution was cancelled
- `failed` - Agent execution failed
- `error` - Agent execution error occurred

## GET `/agents/{agent_id}/state`

Get detailed state information for a specific agent. Returns comprehensive information about agent's current execution state, progress, and context.

**Path Parameters:**

- `agent_id` (string, required): Unique agent identifier (format: `{agent_name}_{uuid}`)

**Request:**

```bash
curl http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/state
```

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

**Response Fields:**

- `agent_id` (string): Unique agent identifier
- `task_messages` (array): Original task messages in OpenAI format
- `state` (string): Current agent state (see Agent States in GET `/agents`)
- `iteration` (integer): Current iteration number (starts from 0)
- `searches_used` (integer): Number of web searches performed so far
- `clarifications_used` (integer): Number of clarification requests made
- `sources_count` (integer): Total number of unique sources collected
- `current_step_reasoning` (object | null): Current step reasoning data (structure varies by agent type)
- `execution_result` (string | null): Final execution result if agent completed, null otherwise

**Error Responses:**

- `404 Not Found`: Agent not found in storage
  ```json
  {
    "detail": "Agent not found"
  }
  ```

## POST `/agents/{agent_id}/provide_clarification`

Provide clarification to an agent that is waiting for input. Resumes agent execution after receiving clarification messages.

**Path Parameters:**

- `agent_id` (string, required): Unique agent identifier (format: `{agent_name}_{uuid}`)

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

**Request Parameters:**

- `messages` (array, required): Clarification messages in OpenAI format (ChatCompletionMessageParam). Can contain multiple messages for complex clarifications.

**Request:**

```bash
curl -X POST "http://localhost:8010/agents/sgr_agent_12345-67890-abcdef/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}]
  }'
```

**Response:**

**Response Headers:**

- `X-Agent-ID` (string): Unique agent identifier
- `Cache-Control`: `no-cache`
- `Connection`: `keep-alive`
- `Content-Type`: `text/event-stream`

**Streaming Response:**

Returns streaming response (SSE format) with continued research after clarification. The agent resumes execution from the point where it requested clarification.

**Error Responses:**

- `404 Not Found`: Agent not found in storage
  ```json
  {
    "detail": "Agent not found"
  }
  ```
- `500 Internal Server Error`: Error during clarification processing
  ```json
  {
    "detail": "Error message"
  }
  ```

**Note:** This endpoint can also be accessed via POST `/v1/chat/completions` by using the agent ID as the `model` parameter when the agent is in `waiting_for_clarification` state.

## DELETE `/agents/{agent_id}`

Cancel a running agent's execution and remove it from storage. If the agent is currently running, it will be cancelled first before removal.

**Path Parameters:**

- `agent_id` (string, required): Unique agent identifier (format: `{agent_name}_{uuid}`)

**Request:**

```bash
curl -X DELETE "http://localhost:8010/agents/sgr_agent_12345-67890-abcdef"
```

**Response:**

```json
{
  "agent_id": "sgr_agent_12345-67890-abcdef",
  "deleted": true,
  "final_state": "cancelled"
}
```

**Response Fields:**

- `agent_id` (string): The ID of the deleted agent
- `deleted` (boolean): Always `true` on successful deletion
- `final_state` (string): Final state of the agent after deletion. Possible values:
  - `"cancelled"` - Agent was running and was cancelled
  - `"completed"` - Agent was already completed
  - `"failed"` - Agent was in failed state
  - `"error"` - Agent was in error state
  - Other states if agent was in a different state

**Behavior:**

- If the agent is currently running, `agent.cancel()` is called first
- The agent's execution task is stopped asynchronously
- The agent state is preserved in `final_state` before removal
- The agent is removed from storage after cancellation/deletion
- Works for agents in any state (running, completed, failed, error, etc.)

**Error Responses:**

- `404 Not Found`: Agent not found in storage
  ```json
  {
    "detail": "Agent not found"
  }
  ```

**Use Cases:**

- Stop a long-running research task that is no longer needed
- Clean up completed agents from storage
- Cancel an agent that is stuck or taking too long
- Free up resources by removing inactive agents
