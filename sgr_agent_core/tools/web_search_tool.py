from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

import httpx
from fastmcp import Client
from pydantic import BaseModel, Field, model_validator
from tavily import AsyncTavilyClient

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import SearchResult, SourceData

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_TAVILY_DEFAULT_URL = "https://api.tavily.com"
_BRAVE_DEFAULT_URL = "https://api.search.brave.com/res/v1/web/search"
_PERPLEXITY_DEFAULT_URL = "https://api.perplexity.ai/search"

_ENGINE_DEFAULT_URLS: dict[str, str] = {
    "tavily": _TAVILY_DEFAULT_URL,
    "brave": _BRAVE_DEFAULT_URL,
    "perplexity": _PERPLEXITY_DEFAULT_URL,
}


class WebSearchConfig(BaseModel, extra="allow"):
    """Configuration for WebSearchTool.

    Defines the search engine, credentials, and limits.
    """

    engine: Literal["tavily", "brave", "perplexity", "parallel"] = Field(
        default="tavily",
        description="Search engine provider to use",
    )
    api_key: str | None = Field(default=None, description="API key for the selected engine")
    api_base_url: str | None = Field(
        default=None,
        description="API base URL for the selected engine (None = engine default)",
    )
    max_searches: int = Field(default=4, ge=0, description="Maximum number of searches")
    max_results: int = Field(default=10, ge=1, description="Maximum number of search results")


# ---------------------------------------------------------------------------
# Tavily
# ---------------------------------------------------------------------------


def _convert_tavily_response(response: dict) -> list[SourceData]:
    """Convert Tavily API response to SourceData list."""
    sources = []
    for i, result in enumerate(response.get("results", [])):
        if not result.get("url", ""):
            continue
        source = SourceData(
            number=i,
            title=result.get("title", ""),
            url=result.get("url", ""),
            snippet=result.get("content", ""),
        )
        if result.get("raw_content", ""):
            source.full_content = result["raw_content"]
            source.char_count = len(source.full_content)
        sources.append(source)
    return sources


async def _search_tavily(
    api_key: str,
    api_base_url: str,
    query: str,
    max_results: int,
    offset: int,
) -> list[SourceData]:
    """Perform search via Tavily API.

    Offset: over-fetch + slice.
    """
    fetch_count = max_results + offset if offset > 0 else max_results
    logger.info(f"Tavily search: '{query}' (max_results={max_results}, offset={offset})")

    client = AsyncTavilyClient(api_key=api_key, api_base_url=api_base_url)
    response = await client.search(query=query, max_results=fetch_count, include_raw_content=False)

    sources = _convert_tavily_response(response)
    if offset > 0:
        sources = sources[offset:]
    return sources[:max_results]


# ---------------------------------------------------------------------------
# Brave
# ---------------------------------------------------------------------------


def _convert_brave_response(response: dict) -> list[SourceData]:
    """Convert Brave Search API response to SourceData list."""
    sources = []
    web_results = response.get("web", {}).get("results", [])
    for i, result in enumerate(web_results):
        url = result.get("url", "")
        if not url:
            continue
        source = SourceData(
            number=i,
            title=result.get("title", ""),
            url=url,
            snippet=result.get("description", ""),
        )
        sources.append(source)
    return sources


async def _search_brave(
    api_key: str,
    api_base_url: str,
    query: str,
    max_results: int,
    offset: int,
) -> list[SourceData]:
    """Perform search via Brave Search API.

    Native offset support.
    """
    capped = min(max_results, 20)
    logger.info(f"Brave search: '{query}' (max_results={capped}, offset={offset})")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params: dict[str, Any] = {"q": query, "count": capped}
    if offset > 0:
        params["offset"] = offset

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_base_url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Brave API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
        raise
    except httpx.RequestError as e:
        logger.error(f"Brave API request error: {e}")
        raise

    return _convert_brave_response(data)


# ---------------------------------------------------------------------------
# Perplexity
# ---------------------------------------------------------------------------


def _convert_perplexity_response(response: dict) -> list[SourceData]:
    """Convert Perplexity Search API response to SourceData list."""
    sources = []
    for i, result in enumerate(response.get("results", [])):
        url = result.get("url", "")
        if not url:
            continue
        source = SourceData(
            number=i,
            title=result.get("title", ""),
            url=url,
            snippet=result.get("snippet", ""),
        )
        sources.append(source)
    return sources


async def _search_perplexity(
    api_key: str,
    api_base_url: str,
    query: str,
    max_results: int,
    offset: int,
) -> list[SourceData]:
    """Perform search via Perplexity API.

    Offset: over-fetch + slice.
    """
    fetch_count = max_results + offset if offset > 0 else max_results
    logger.info(f"Perplexity search: '{query}' (max_results={max_results}, offset={offset})")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"query": query, "max_results": fetch_count}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_base_url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Perplexity API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
        raise
    except httpx.RequestError as e:
        logger.error(f"Perplexity API request error: {e}")
        raise

    sources = _convert_perplexity_response(data)
    if offset > 0:
        sources = sources[offset:]
    return sources[:max_results]


# ---------------------------------------------------------------------------
# Engine handler mapping
# ---------------------------------------------------------------------------

SearchHandler = Callable[..., Awaitable[list[SourceData]]]

_ENGINE_HANDLERS: dict[str, SearchHandler] = {
    "tavily": _search_tavily,
    "brave": _search_brave,
    "perplexity": _search_perplexity,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rearrange_sources(sources: list[SourceData], starting_number: int = 1) -> list[SourceData]:
    """Renumber sources sequentially starting from given number."""
    for i, source in enumerate(sources, starting_number):
        source.number = i
    return sources


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------


class WebSearchTool(BaseTool):
    """Search the web for real-time information about any topic.

    Single search tool with pluggable engine (tavily, brave, perplexity).
    Engine is selected via tool config ``engine`` field.

    Use this tool when you need up-to-date information that might not be
    available in your training data, or when you need to verify current facts.
    The search results will include relevant snippets and URLs from web pages.
    This is particularly useful for questions about current events, technology
    updates, or any topic that requires recent information.
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

    config_model = WebSearchConfig

    reasoning: str = Field(description="Why this search is needed and what to expect")
    query: str = Field(description="Search query in same language as user request")
    max_results: int = Field(
        description="Maximum results. How much of the web results selection you want to retrieve",
        default=5,
        ge=1,
        le=20,
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of results to skip from the beginning."
            " Use for pagination: first call offset=0, next call offset=5, etc."
        ),
    )

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs: Any) -> str:
        """Execute web search using the configured search engine."""
        search_config = WebSearchConfig(**kwargs)

        engine = search_config.engine
        logger.info(f"Search query: '{self.query}' (engine={engine})")

        handler = _ENGINE_HANDLERS.get(engine)
        if handler is None:
            raise ValueError(f"Unsupported search engine: {engine}")

        api_key = search_config.api_key
        if not api_key:
            raise ValueError(f"api_key is required for engine '{engine}'")

        api_base_url = search_config.api_base_url or _ENGINE_DEFAULT_URLS[engine]

        effective_limit = min(self.max_results, search_config.max_results)

        sources = await handler(
            api_key=api_key,
            api_base_url=api_base_url,
            query=self.query,
            max_results=effective_limit,
            offset=self.offset,
        )

        sources = _rearrange_sources(sources, starting_number=len(context.sources) + 1)

        for source in sources:
            context.sources[source.url] = source

        search_result = SearchResult(
            query=self.query,
            answer=None,
            citations=sources,
            timestamp=datetime.now(),
        )
        context.searches.append(search_result)

        formatted_result = f"Search Query: {search_result.query}\n\n"
        formatted_result += "Search Results (titles, links, short snippets):\n\n"

        for source in sources:
            snippet = source.snippet[:100] + "..." if len(source.snippet) > 100 else source.snippet
            formatted_result += f"{str(source)}\n{snippet}\n\n"

        context.searches_used += 1
        logger.debug(formatted_result)
        return formatted_result


_PARALLEL_MCP_URL = "https://search.parallel.ai/mcp"


class ParallelWebSearchTool(BaseTool):
    """Search the web with Parallel Search MCP.

    This tool is selected only when ``web_search_tool.engine`` is explicitly
    set to ``parallel``. Search objectives and search queries are sent to
    Parallel; URL fetching is not registered by this integration.
    """

    tool_name = "parallel_web_search"

    objective: str | None = Field(
        default=None,
        description="Natural-language objective describing what the search should accomplish",
    )
    search_queries: list[str] | None = Field(
        default=None,
        description="Specific web search queries that support the objective",
    )

    @model_validator(mode="after")
    def normalize_search_input(self):
        objective = self.objective.strip() if self.objective else ""
        queries = [query.strip() for query in (self.search_queries or []) if query.strip()]
        if not objective and not queries:
            raise ValueError("objective or at least one search query is required")
        if not objective:
            objective = queries[0]
        if not queries:
            queries = [objective]
        self.objective = objective
        self.search_queries = queries
        return self

    @staticmethod
    def _validate_hosted_tools(tools: list[Any]) -> None:
        advertised = {tool.name: tool.inputSchema for tool in tools}
        search_schema = advertised.get("web_search")
        fetch_schema = advertised.get("web_fetch")
        if not search_schema or not fetch_schema:
            raise RuntimeError("Parallel Search MCP did not advertise web_search and web_fetch")

        search_properties = search_schema.get("properties", {})
        objective_schema = search_properties.get("objective", {})
        queries_schema = search_properties.get("search_queries", {})
        fetch_urls_schema = fetch_schema.get("properties", {}).get("urls", {})
        if (
            objective_schema.get("type") != "string"
            or queries_schema.get("type") != "array"
            or queries_schema.get("items", {}).get("type") != "string"
            or not {"objective", "search_queries"}.issubset(search_schema.get("required", []))
            or fetch_urls_schema.get("type") != "array"
            or fetch_urls_schema.get("items", {}).get("type") != "string"
            or "urls" not in fetch_schema.get("required", [])
        ):
            raise RuntimeError("Parallel Search MCP advertised an unexpected tool schema")

    @staticmethod
    def _result_data(result: Any) -> dict[str, Any]:
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        for content in getattr(result, "content", []):
            text = getattr(content, "text", None)
            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                except (TypeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    return parsed
        raise RuntimeError("Parallel Search MCP returned no structured search result")

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs: Any) -> str:
        payload = {"objective": self.objective, "search_queries": self.search_queries}
        try:
            async with Client(_PARALLEL_MCP_URL) as client:
                self._validate_hosted_tools(await client.list_tools())
                result = await client.call_tool("web_search", payload)
        except Exception as exc:
            logger.error("Parallel Search MCP request failed: %s", exc)
            return f"Error: {exc}"

        if getattr(result, "is_error", False):
            raise RuntimeError("Parallel Search MCP returned a tool error")
        data = self._result_data(result)
        raw_results = data.get("results", data.get("search_results", []))
        if not isinstance(raw_results, list):
            raise RuntimeError("Parallel Search MCP returned malformed search results")

        sources = []
        for item in raw_results:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str) or not item["url"]:
                continue
            excerpts = item.get("excerpts")
            if not isinstance(excerpts, list) or not all(isinstance(excerpt, str) for excerpt in excerpts):
                raise RuntimeError("Parallel Search MCP returned malformed excerpts")
            sources.append(
                SourceData(
                    number=0,
                    title=item.get("title"),
                    url=item["url"],
                    snippet="\n".join(excerpts),
                )
            )

        search_config = WebSearchConfig(**kwargs)
        sources = sources[: search_config.max_results]
        sources = _rearrange_sources(sources, starting_number=len(context.sources) + 1)
        for source in sources:
            context.sources[source.url] = source
        query = self.search_queries[0]
        search_result = SearchResult(query=query, citations=sources, timestamp=datetime.now())
        context.searches.append(search_result)
        context.searches_used += 1

        formatted = f"Search Objective: {self.objective}\nSearch Queries: {', '.join(self.search_queries)}\n\n"
        formatted += "Search Results (titles, links, excerpts):\n\n"
        for source in sources:
            formatted += f"{source}\n{source.snippet}\n\n"
        return formatted
