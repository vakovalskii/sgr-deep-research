# Open-WebUI Adapter for SGR Agent Core

This adapter enables seamless integration of SGR Agent Core with Open-WebUI frontend.

## 🎯 Purpose

The adapter solves several integration challenges between SGR Agent Core and Open-WebUI:

1. **Duplicate Tool Calls** - Filters duplicate tool calls from LLM to prevent JSON concatenation errors
2. **Clean Final Answers** - Sends only the answer text for FinalAnswerTool (instead of full JSON)
3. **HTML Formatting** - Uses HTML `<details>` tags for better tool call display in Open-WebUI
4. **Conversation History** - Extracts and preserves clean conversation history across turns
5. **Streaming Optimization** - Optimized streaming for Open-WebUI's SSE protocol

## 📁 Structure

```
adapters/
├── __init__.py                      # Exports main classes
├── openwebui_agent.py              # Main adapter class
├── streaming.py                     # Open-WebUI specific streaming
├── conversation_history.py          # History extraction logic
└── tools/
    ├── __init__.py
    ├── reasoning_tool_owui.py      # Reasoning tool with clean fields
    └── final_answer_tool_owui.py   # Final answer trigger tool
```

## 🔧 Components

### OpenWebUIToolCallingAgent

Main adapter class that extends `SGRToolCallingAgent` with Open-WebUI specific behavior:

- **Reasoning Phase**: Sends reasoning as text chunk + details tag
- **Action Phase**: Handles tool execution with proper start/result streaming
- **Final Answer**: Generates streaming LLM completion for final answer
- **Stream Management**: Prevents duplicate finish() calls

```python
from sgr_deep_research.adapters import OpenWebUIToolCallingAgent

agent = OpenWebUIToolCallingAgent(
    task="Research quantum computing",
    openai_client=client,
    agent_config=config,
    toolkit=[ReasoningToolOWUI, FinalAnswerToolOWUI, WebSearchTool],
)
```

### OpenWebUIStreamingGenerator

Extended streaming generator with HTML details tag support:

- `add_tool_call_start()` - Shows tool execution start with shimmer animation
- `add_tool_call_with_result()` - Shows completed tool call with result

```python
from sgr_deep_research.adapters.streaming import OpenWebUIStreamingGenerator

generator = OpenWebUIStreamingGenerator(model="gpt-4o")
generator.add_tool_call_start("1-reasoning", "reasoning", '{"reasoning": "..."}')
generator.add_tool_call_with_result("1-reasoning", "reasoning", '{"reasoning": "..."}', "Complete")
```

### Conversation History Extraction

Extracts clean conversation history from Open-WebUI messages:

- Filters out tool calls and intermediate steps
- Keeps only final assistant answers
- Reduces context size significantly (often 80%+ reduction)
- Uses multiple strategies to extract final answers

```python
from sgr_deep_research.adapters import extract_conversation_history

history = extract_conversation_history(request.messages)
# Returns: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
```

### Custom Tools

#### ReasoningToolOWUI

Reasoning tool with clean field names for Open-WebUI display:

```python
class ReasoningToolOWUI(BaseTool):
    reasoning: str              # Brief reasoning (2-3 sentences)
    current_situation: str      # Current state assessment
    plan_status: str           # Status of current plan
    enough_data: bool          # Sufficient data collected?
    next_step: str             # Next immediate action
    remaining_steps: list[str] # Remaining steps (1-2)
    task_completed: bool       # Is task finished?
```

#### FinalAnswerToolOWUI

Trigger tool for final answer generation:

```python
class FinalAnswerToolOWUI(BaseTool):
    reasoning: str          # Why ready to answer
    ready_to_answer: bool   # Set to True when ready
```

When `ready_to_answer=True`, the agent generates a comprehensive final answer using LLM completion without tools.

## 🚀 Usage

### 1. Configuration

Add to `agents.yaml`:

```yaml
openwebui_research_agent:
  base_class: "OpenWebUIToolCallingAgent"
  
  llm:
    model: "gpt-4o"
    temperature: 0.2
    max_tokens: 16000
  
  search:
    max_searches: 8
    max_results: 15
    content_limit: 2000
  
  execution:
    max_iterations: 25
    max_clarifications: 5
    max_searches: 8
  
  tools:
    - "ReasoningToolOWUI"
    - "FinalAnswerToolOWUI"
    - "WebSearchTool"
    - "ExtractPageContentTool"
```

### 2. API Integration

The adapter is automatically used when the agent definition specifies `OpenWebUIToolCallingAgent` as base_class:

```python
# In endpoints.py
from sgr_deep_research.adapters import OpenWebUIToolCallingAgent, extract_conversation_history

# Extract conversation history
conversation_history = extract_conversation_history(request.messages)

# Create agent (will use OpenWebUIToolCallingAgent if specified in definition)
agent = await AgentFactory.create(agent_def, task)

# Inject conversation history
if conversation_history:
    agent.conversation.extend(conversation_history)

# Execute and stream
_ = asyncio.create_task(agent.execute())
return StreamingResponse(agent.streaming_generator.stream(), media_type="text/event-stream")
```

### 3. Open-WebUI Display

Tool calls are displayed as collapsible details:

```html
<details type="tool_calls" done="false" id="1-reasoning" name="reasoning">
  <summary>Executing reasoning...</summary>
</details>

<details type="tool_calls" done="true" id="1-reasoning-result" name="reasoning">
  <summary>View Result from reasoning</summary>
</details>
```

## 🔍 Key Features

### 1. Duplicate Tool Call Prevention

Open-WebUI sometimes sends duplicate requests. The adapter filters these:

```python
# In endpoints.py
if request.messages and request.messages[-1].role != "user":
    logger.info("⚠️  Last message is not from user - ignoring duplicate request")
    return StreamingResponse(empty_stream(), media_type="text/event-stream")
```

### 2. Context Size Reduction

Conversation history extraction reduces context size dramatically:

```
Original: 15,234 chars (full tool calls, reasoning, intermediate steps)
Filtered: 2,847 chars (only final answers)
Reduction: 81.3% saved
```

### 3. Streaming Optimization

The adapter optimizes streaming for Open-WebUI:

- **Reasoning**: Text chunk + details tag
- **Tools with execute**: Start tag (done=false) → Result tag (done=true)
- **Tools without execute**: Single tag (done=true)
- **Final answer**: Streaming LLM completion

### 4. Clean Final Answers

FinalAnswerToolOWUI triggers LLM-generated final answer:

```python
async def _generate_final_answer_streaming(self) -> None:
    """Generate final answer using LLM completion without tools."""
    messages = [
        {"role": "system", "content": "Provide comprehensive final answer..."},
        *self.conversation,
    ]
    
    stream = await self.openai_client.chat.completions.create(
        model=self.config.llm.model,
        messages=messages,
        stream=True,
    )
    
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            self.streaming_generator.add_chunk_from_str(content)
```

## 🐛 Debugging

Enable detailed logging:

```python
import logging
logging.getLogger("sgr_deep_research.adapters").setLevel(logging.DEBUG)
```

Logs show:

- 🔍 Conversation history extraction steps
- 📤 Tool call streaming (start/result)
- 💭 Reasoning content
- 🎯 Final answer generation
- 💾 Context size reduction stats

## 📊 Performance

Typical metrics for a research task:

- **Iterations**: 3-5
- **Tool calls**: 6-12
- **Context reduction**: 70-85%
- **Response time**: 15-45 seconds
- **Token usage**: 5,000-15,000 tokens

## 🔗 Integration Points

### 1. Agent Factory

```python
# In app.py
from sgr_deep_research.adapters import OpenWebUIToolCallingAgent  # noqa: F401

# This registers the adapter with AgentFactory
```

### 2. API Endpoints

```python
# In endpoints.py
from sgr_deep_research.adapters import OpenWebUIToolCallingAgent, extract_conversation_history

# Extract history
conversation_history = extract_conversation_history(request.messages)

# Create agent (uses OpenWebUIToolCallingAgent if specified)
agent = await AgentFactory.create(agent_def, task)

# Inject history
agent.conversation.extend(conversation_history)
```

### 3. Tool Registry

```python
# Tools are automatically registered via ToolRegistry
from sgr_deep_research.adapters.tools import ReasoningToolOWUI, FinalAnswerToolOWUI
```

## 🎨 Customization

### Custom Reasoning Fields

Extend `ReasoningToolOWUI` with custom fields:

```python
class CustomReasoningTool(ReasoningToolOWUI):
    confidence_score: float = Field(description="Confidence in reasoning")
    sources_used: list[str] = Field(description="Sources consulted")
```

### Custom Streaming Format

Override streaming methods in `OpenWebUIToolCallingAgent`:

```python
class CustomAgent(OpenWebUIToolCallingAgent):
    async def _reasoning_phase(self) -> ReasoningToolOWUI:
        # Custom reasoning display logic
        pass
```

## 📝 Notes

1. **Tool Execution**: Tools with real `execute()` logic (WebSearchTool, ExtractPageContentTool) send start + result tags. Other tools send single result tag.

2. **Final Answer**: FinalAnswerToolOWUI doesn't send any details tag - it triggers streaming LLM completion for clean final answer.

3. **Conversation History**: History extraction is critical for multi-turn conversations. Without it, context grows exponentially.

4. **Stream Finish**: The adapter prevents duplicate `finish()` calls by tracking `_stream_finished` flag.

## 🚦 Status

✅ **Production Ready**

The adapter has been tested with:
- Multiple conversation turns
- Complex research tasks
- Various tool combinations
- Error scenarios
- Context size limits

## 📚 References

- [SGR Agent Core](../../README.md)
- [Open-WebUI Documentation](https://docs.openwebui.com/)
- [OpenAI Streaming API](https://platform.openai.com/docs/api-reference/streaming)

