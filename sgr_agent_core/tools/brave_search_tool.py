from sgr_agent_core.tools.base_search_tool import _BaseSearchTool


class BraveSearchTool(_BaseSearchTool):
    """Search the web using Brave search engine. Brave Search provides privacy-
    focused search results with native pagination support. Use this tool when
    you specifically want to search with Brave.

    Returns: Page titles, URLs, and short snippets
    Best for: Privacy-focused search, efficient pagination via native offset

    Usage:
        - Use SPECIFIC terms and context in queries
        - Search queries in SAME LANGUAGE as user request
        - Brave supports efficient pagination with offset parameter
    """

    _default_engine = "brave"
