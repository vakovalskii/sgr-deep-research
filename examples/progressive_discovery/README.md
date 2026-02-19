# Progressive Tool Discovery

Example agent demonstrating dynamic tool discovery for SGR Agent Core.

## Problem

When using multiple MCP servers (Jira, Confluence, GitHub, GDrive), each adds dozens of tools. With ~60 tools the LLM context becomes bloated — local models can't handle it, and paid APIs waste tokens on irrelevant tool descriptions.

## Solution

The agent starts with a minimal set of **system tools** (reasoning, planning, clarification, final answer) and dynamically discovers additional tools via `SearchToolsTool`.

```
User query → Agent reasons → needs web search → calls SearchToolsTool("search the web")
→ WebSearchTool discovered and added to active toolkit → Agent uses WebSearchTool
```

### How it works

1. **Init**: Toolkit is split into system tools (subclasses of `SystemBaseTool`) and discoverable tools
2. **Runtime**: Only system tools + already discovered tools are sent to LLM
3. **Discovery**: Agent calls `SearchToolsTool` with a natural language query
4. **Matching**: `ToolFilterService` uses BM25 ranking + regex keyword overlap to find relevant tools
5. **Activation**: Matched tools are added to the active toolkit for subsequent calls

### Key components

| Component                   | Description                                                   |
| --------------------------- | ------------------------------------------------------------- |
| `ProgressiveDiscoveryAgent` | Agent subclass that manages system/discovered tool split      |
| `SearchToolsTool`           | Meta-tool for discovering new tools by capability description |
| `ToolFilterService`         | Stateless BM25 + regex matching service                       |

## Usage

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your API key and MCP servers
sgr --config-file config.yaml
```

## Architecture

```
ProgressiveDiscoveryAgent
├── self.toolkit = [ReasoningTool, SearchToolsTool, ...]  (system tools)
├── context.all_tools = [WebSearchTool, ...]  (discoverable)
└── context.discovered_tools = []  (accumulates at runtime)
```

`context` is a `ProgressiveDiscoveryContext(AgentContext)` — extends the base context with discovery-specific fields.

`_get_active_tools()` returns `system_tools + discovered_tools` — used by both `_prepare_tools()` and `_prepare_context()`.
