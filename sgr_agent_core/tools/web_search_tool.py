from sgr_agent_core.tools.base_search_tool import _BaseSearchTool


class WebSearchTool(_BaseSearchTool):
    """Search the web for real-time information about any topic.
    Use this tool when you need up-to-date information that might not be available in your training data,
    or when you need to verify current facts.
    The search results will include relevant snippets and URLs from web pages.
    This is particularly useful for questions about current events, technology updates,
    or any topic that requires recent information.
    Use for: Public information, news, market trends, external APIs, general knowledge
    Returns: Page titles, URLs, and short snippets (100 characters)
    Best for: Quick overview, finding relevant pages

    Usage:
        - Use SPECIFIC terms and context in queries
        - For acronyms, add context: "SGR Schema-Guided Reasoning"
        - Use quotes for exact phrases: "Structured Output OpenAI"
        - Search queries in SAME LANGUAGE as user request
        - For date/number questions, include specific year/context in query
        - Use ExtractPageContentTool to get full content from found URLs

    IMPORTANT FOR FACTUAL QUESTIONS:
        - Search snippets often contain direct answers - check them carefully
        - For questions with specific dates/numbers, snippets may be more accurate than full pages
        - If the snippet directly answers the question, you may not need to extract the full page
    """
