## WebSearchTool

**Type:** Auxiliary Tool
**Source:** [sgr_agent_core/tools/web_search_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/web_search_tool.py)

Searches the web for real-time information using Tavily Search API.

The `tavily` engine needs the `search` extra (`pip install "sgr-agent-core[search]"`).
The `brave` and `perplexity` engines talk plain HTTP and work on the core install.

**Parameters**

- `reasoning` (str) - why this search is needed and what to expect
- `query` (str) - search query in same language as user request
- `max_results` (int, default=5, range 1-10) - maximum number of results to retrieve

**Behavior**

- Executes search via TavilySearchService
- Adds found sources to `context.sources` dictionary
- Creates SearchResult and appends to `context.searches`
- Increments `context.searches_used`
- Returns formatted string with search query and results (titles, links, snippets)

**Usage**

Use for finding up-to-date information, verifying facts, researching current events, technology updates, or any topic requiring recent information.

**Best practices**

- Use specific terms and context in queries
- For acronyms, add context: "SGR Schema-Guided Reasoning"
- Use quotes for exact phrases: "Structured Output OpenAI"
- Keep search queries in the same language as the user request
- For date or number questions, include specific year or context in query
- Search snippets often contain direct answers, review them carefully

**Configuration**

```yaml
search:
  tavily_api_key: "your-tavily-api-key"  # Required: Tavily API key
  tavily_api_base_url: "https://api.tavily.com"  # Tavily API URL
  max_searches: 4  # Maximum number of search operations
  max_results: 10  # Maximum results in search query (overrides tool's max_results if lower)
```

After reaching `max_searches`, the tool is automatically removed from available tools.

**Example**

```yaml
agents:
  research_agent:
    search:
      max_searches: 6
      max_results: 15
    tools:
      - "web_search_tool"
```
