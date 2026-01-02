## 🧶 Agent Execution Sequence

The following diagram shows the complete SGR agent workflow with interruption and clarification support:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Server
    participant Agent as SGR Agent
    participant LLM as LLM
    participant Tools as Research Tools

    Note over Client, Tools: SGR Agent Core - Agent Workflow

    Client->>API: POST /v1/chat/completions<br/>{"model": "sgr_agent", "messages": [...]}

    API->>Agent: Create new SGR Agent<br/>with unique ID
    Note over Agent: State: INITED

    Agent->>Agent: Initialize context<br/>and conversation history

    loop SGR Reasoning Loop (max 6 steps)
        Agent->>Agent: Prepare tools based on<br/>current context limits
        Agent->>LLM: Structured Output Request<br/>with NextStep schema

        LLM-->>API: Streaming chunks
        API-->>Client: SSE stream with<br/>agent_id in model field

        LLM->>Agent: Parsed NextStep result

        alt Tool: Clarification
            Note over Agent: State: WAITING_FOR_CLARIFICATION
            Agent->>Tools: Execute clarification tool
            Tools->>API: Return clarifying questions
            API-->>Client: Stream clarification questions

            Client->>API: POST /v1/chat/completions<br/>{"model": "agent_id", "messages": [...]}
            API->>Agent: provide_clarification()
            Note over Agent: State: RESEARCHING
            Agent->>Agent: Add clarification to context

        else Tool: GeneratePlan
            Agent->>Tools: Execute plan generation
            Tools->>Agent: Research plan created

        else Tool: WebSearch
            Agent->>Tools: Execute web search
            Tools->>Tools: Tavily API call
            Tools->>Agent: Search results + sources
            Agent->>Agent: Update context with sources

        else Tool: AdaptPlan
            Agent->>Tools: Execute plan adaptation
            Tools->>Agent: Updated research plan

        else Tool: CreateReport
            Agent->>Tools: Execute report creation
            Tools->>Tools: Generate comprehensive<br/>report with citations
            Tools->>Agent: Final research report

        else Tool: ReportCompletion
            Note over Agent: State: COMPLETED
            Agent->>Tools: Execute completion
            Tools->>Agent: Task completion status
        end

        Agent->>Agent: Add tool result to<br/>conversation history
        API-->>Client: Stream tool execution result

        break Task Completed
            Agent->>Agent: Break execution loop
        end
    end

    Agent->>API: Finish streaming
    API-->>Client: Close SSE stream

    Note over Client, Tools: Agent remains accessible<br/>via agent_id for further clarifications
```

## 🤖 Schema-Guided Reasoning Capabilities:

1. **🤔 Clarification** - clarifying questions when unclear
2. **📋 Plan Generation** - research plan creation
3. **🔍 Web Search** - internet information search
4. **🔄 Plan Adaptation** - plan adaptation based on results
5. **📝 Report Creation** - detailed report creation
6. **✅ Final Answer** - task completion
