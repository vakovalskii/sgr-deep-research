## 🚀 <strong>Python OpenAI Client Examples</strong> - Complete integration guide with streaming & clarifications</summary>

Simple Python examples for using OpenAI client with SGR Agent Core system.

### Prerequisites

```bash
pip install openai
```

### Example 1: Basic Research Request

Simple research query without clarifications.

```python
from openai import OpenAI

# Initialize client
client = OpenAI(
    base_url="http://localhost:8010/v1",
    api_key="dummy",  # Not required for local server
)

# Make research request
response = client.chat.completions.create(
    model="sgr-agent",
    messages=[{"role": "user", "content": "Research BMW X6 2025 prices in Russia"}],
    stream=True,
    temperature=0.4,
)

# Print streaming response
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Example 2: Research with Clarification Support

Handle agent clarification requests and continue conversation.

```python
import json
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8010/v1", api_key="dummy")

# Step 1: Initial research request
print("Starting research...")
response = client.chat.completions.create(
    model="sgr-agent",
    messages=[{"role": "user", "content": "Research AI market trends"}],
    stream=True,
    temperature=0,
)

agent_id = None
clarification_questions = []

# Process streaming response
for chunk in response:
    # Extract agent ID from model field
    if chunk.model and chunk.model.startswith("sgr_agent_"):
        agent_id = chunk.model
        print(f"\nAgent ID: {agent_id}")

    # Check for clarification requests
    if chunk.choices[0].delta.tool_calls:
        for tool_call in chunk.choices[0].delta.tool_calls:
            if tool_call.function and tool_call.function.name == "clarification":
                args = json.loads(tool_call.function.arguments)
                clarification_questions = args.get("questions", [])

    # Print content
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# Step 2: Handle clarification if needed
if clarification_questions and agent_id:
    print(f"\n\nClarification needed:")
    for i, question in enumerate(clarification_questions, 1):
        print(f"{i}. {question}")

    # Provide clarification
    clarification = "Focus on LLM market trends for 2024-2025, global perspective"
    print(f"\nProviding clarification: {clarification}")

    # Continue with agent ID
    response = client.chat.completions.create(
        model=agent_id,  # Use agent ID as model
        messages=[{"role": "user", "content": clarification}],
        stream=True,
        temperature=0,
    )

    # Print final response
    for chunk in response:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")

print("\n\nResearch completed!")
```

### Example 3: Research Request with Image

Send a research request with a local image file attachment.

```python
import base64
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8010/v1", api_key="dummy")

# Read local image file and encode to base64
with open("chart.png", "rb") as image_file:
    image_data = base64.b64encode(image_file.read()).decode("utf-8")
    image_base64 = f"data:image/png;base64,{image_data}"

# Research request with local image
response = client.chat.completions.create(
    model="sgr-agent",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze this chart and research the trends shown"},
            {"type": "image_url", "image_url": {"url": image_base64}}
        ]
    }],
    stream=True,
    temperature=0.4,
)

# Print streaming response
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

**Image Formats Supported:**
- Image URLs (HTTP/HTTPS)
- Base64 encoded images (`data:image/jpeg;base64,...` or `data:image/png;base64,...`)

#### Usage Notes

- Replace `localhost:8010` with your server URL
- The `api_key` can be any string for local server
- Agent ID is returned in the `model` field during streaming
- Clarification questions are sent via `tool_calls` with function name `clarification`
- Use the agent ID as model name to continue conversation

______________________________________________________________________

## <summary>⚡ <strong>cURL API Examples</strong> - Direct HTTP requests with agent interruption & clarification flow</summary>

The system provides a fully OpenAI-compatible API with advanced agent interruption and clarification capabilities.

### Basic Research Request

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

### Agent Interruption & Clarification Flow

When the agent needs clarification, it returns a unique agent ID in the streaming response model field. You can then continue the conversation using this agent ID.

#### Step 1: Initial Request

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

#### Step 2: Agent Requests Clarification

The streaming response includes the agent ID in the model field:

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

#### Step 3: Continue with Agent ID

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

### Agent Management

```bash
# Get all active agents
curl http://localhost:8010/agents

# Get specific agent state
curl http://localhost:8010/agents/{agent_id}/state

# Direct clarification endpoint
curl -X POST "http://localhost:8010/agents/{agent_id}/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}],
    "stream": true
  }'
```
