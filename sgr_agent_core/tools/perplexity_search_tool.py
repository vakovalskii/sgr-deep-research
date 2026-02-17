from sgr_agent_core.tools.base_search_tool import _BaseSearchTool


class PerplexitySearchTool(_BaseSearchTool):
    """Search the web using Perplexity AI search engine. Perplexity provides
    AI-powered search with synthesized answers and source citations. Use this
    tool when you specifically want to search with Perplexity.

    Returns: Page titles, URLs, and AI-synthesized snippets
    Best for: Getting AI-synthesized answers with source citations

    Usage:
        - Use SPECIFIC terms and context in queries
        - Search queries in SAME LANGUAGE as user request
        - Results include AI-generated summary alongside source URLs
    """

    _default_engine = "perplexity"
