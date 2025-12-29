## 👁 The Problem with Function Calling on Local Models (ReAct Agents)

**Reality Check:** Function Calling works great on OpenAI/Anthropic (80+ [BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html) scores) but fails dramatically on local models \<32B parameters when using true ReAct agents with `tool_mode="auto"`, where the model itself decides when to call tools.

**BFCL Benchmark Results for Qwen3 Models:**

- `Qwen3-8B (FC)`: Only 15% accuracy in Agentic Web Search mode ([BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html) benchmark)
- `Qwen3-4B (FC)`: Only 2% accuracy in Agentic Web Search mode
- `Qwen3-1.7B (FC)`: Only 4.5% accuracy in Agentic Web Search mode
- Even with native FC support, smaller models struggle with deciding **WHEN** to call tools
- Common result: `{"tool_calls": null, "content": "Text instead of tool call"}`

**Note:** Our team is currently working on creating a specialized benchmark for SGR vs ReAct performance on smaller models. Initial testing confirms that the SGR pipeline enables even smaller models to follow complex task workflows.

## 👁 SGR Solution: Forced Reasoning → Deterministic Execution

```python
# Phase 1: Structured Output reasoning (100% reliable)
reasoning = model.generate(format="json_schema")
# {"action": "search", "query": "BMW X6 prices", "reason": "need current data"}

# Phase 2: Deterministic execution (no model uncertainty)
result = execute_plan(reasoning.actions)
```

## 👁 Architecture by Model Size

| Model Size | Recommended Approach         | FC Accuracy | Why Choose This         |
| ---------- | ---------------------------- | ----------- | ----------------------- |
| **\<14B**  | Pure SGR + Structured Output | 15-25%      | FC practically unusable |
| **14-32B** | SGR + FC hybrid              | 45-65%      | Best of both worlds     |
| **32B+**   | Native FC with SGR fallback  | 85%+        | FC works reliably       |

## 👁 When to Use SGR vs Function Calling

| Use Case                        | Best Approach    | Why                                              |
| ------------------------------- | ---------------- | ------------------------------------------------ |
| **Data analysis & structuring** | SGR              | Controlled reasoning with visibility             |
| **Document processing**         | SGR              | Step-by-step analysis with justification         |
| **Local models (\<32B)**        | SGR              | Forces reasoning regardless of model limitations |
| **Multi-agent systems**         | Function Calling | Native agent interruption support                |
| **External API interactions**   | Function Calling | Direct tool access pattern                       |
| **Production monitoring**       | SGR              | All reasoning steps visible and loggable         |

## 👁 Real-World Results

**Initial Testing Results:**

- SGR enables even small models to follow structured workflows
- SGR pipeline provides deterministic execution regardless of model size
- SGR forces reasoning steps that ReAct leaves to model discretion

**Planned Benchmarking:**

- We're developing a comprehensive benchmark comparing SGR vs ReAct across model sizes
- Initial testing shows promising results for SGR on models as small as 4B parameters
- Full metrics and performance comparison coming soon

## 👁 Hybrid Approach: The Best of Both Worlds

The optimal solution for many production systems is a hybrid approach:

1. **SGR for decision making** - Determine which tools to use
2. **Function Calling for execution** - Get data and provide agent-like experience
3. **SGR for final processing** - Structure and format results

This hybrid approach works particularly well for models in the 14-32B range, where Function Calling works sometimes but isn't fully reliable.

**Bottom Line:** Don't force \<32B models to pretend they're GPT-4o in ReAct-style agentic workflows with `tool_mode="auto"`. Let them think structurally through SGR, then execute deterministically.
