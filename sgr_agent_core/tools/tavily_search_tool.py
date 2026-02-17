from sgr_agent_core.tools.base_search_tool import _BaseSearchTool


class TavilySearchTool(_BaseSearchTool):
    """Search the web using Tavily search engine. Tavily provides high-quality
    search results with optional raw content extraction. Use this tool when you
    specifically want to search with Tavily.

    Returns: Page titles, URLs, and short snippets
    Best for: General web search, research queries

    Usage:
        - Use SPECIFIC terms and context in queries
        - Search queries in SAME LANGUAGE as user request
        - Use ExtractPageContentTool to get full content from found URLs
    """

    _default_engine = "tavily"
