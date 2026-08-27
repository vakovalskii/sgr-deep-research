## ExtractPageContentTool

**Type:** Auxiliary Tool
**Source:** [sgr_agent_core/tools/extract_page_content_tool.py](https://github.com/vamplabAI/sgr-agent-core/blob/main/sgr_agent_core/tools/extract_page_content_tool.py)

Extracts full detailed content from specific web pages using Tavily Extract API.

Needs the `search` extra: `pip install "sgr-agent-core[search]"`.

**Parameters**

- `reasoning` (str) - why extract these specific pages
- `urls` (list[str], 1-5 items) - list of URLs to extract full content from

**Behavior**

- Extracts full content from specified URLs via TavilySearchService
- Updates existing sources in `context.sources` with full content
- For new URLs, adds them with sequential numbering
- Returns formatted string with extracted content preview (limited by `content_limit`)

**Usage**

Call after `web_search_tool` to get detailed information from promising URLs found in search results.

**Important warnings**

- Extracted pages may show data from different years or time periods than requested
- Always verify that extracted content matches the temporal context of the question
- If extracted content contradicts search snippet, prefer snippet for factual questions
- For date or number questions, cross-check extracted values with search snippets

**Configuration**

```yaml
search:
  tavily_api_key: "your-tavily-api-key"  # Required: Tavily API key
  tavily_api_base_url: "https://api.tavily.com"  # Tavily API URL
  content_limit: 1500  # Content character limit per source (truncates extracted content)
```

**Example**

```yaml
agents:
  research_agent:
    search:
      content_limit: 2000  # Increase content limit for more detailed extraction
    tools:
      - "web_search_tool"
      - "extract_page_content_tool"
```
