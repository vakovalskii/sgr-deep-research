from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field

from sgr_agent_core.agent_definition import AgentConfig, SearchConfig
from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.models import SearchResult, SourceData
from sgr_agent_core.services.registry import SearchProviderRegistry
from sgr_agent_core.utils import config_from_kwargs

if TYPE_CHECKING:
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class _BaseSearchTool(BaseTool):
    """Base class for all search tools.

    Provides shared fields (reasoning, query, max_results, offset) and
    common __call__ logic. Concrete tools override _default_engine and
    docstring.

    Provider-specific API logic lives in concrete tools as @staticmethod
    _search() methods, dispatched via SearchProviderRegistry by engine
    name.
    """

    _default_engine: ClassVar[str | None] = None

    config_model = SearchConfig
    base_config_attr = "search"

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

    @staticmethod
    def _rearrange_sources(sources: list[SourceData], starting_number: int = 1) -> list[SourceData]:
        """Renumber sources sequentially starting from given number."""
        for i, source in enumerate(sources, starting_number):
            source.number = i
        return sources

    async def __call__(self, context: AgentContext, config: AgentConfig, **kwargs: Any) -> str:
        """Execute web search using the configured search engine.

        Search settings are taken from kwargs (tool config) with
        fallback to config.search.
        """
        # If this tool has a hardcoded engine, force it
        if self._default_engine is not None:
            kwargs.setdefault("engine", self._default_engine)

        search_config = config_from_kwargs(
            SearchConfig,
            config.search if config else None,
            dict(kwargs),
        )
        logger.info(f"Search query: '{self.query}' (engine={search_config.engine})")

        provider_cls = SearchProviderRegistry.get(search_config.engine)
        if provider_cls is None:
            raise ValueError(f"Unsupported search engine: {search_config.engine}")

        max_results_limit = search_config.max_results
        effective_limit = min(self.max_results, max_results_limit)

        # Each provider handles offset internally:
        # Brave uses native API offset, Tavily/Perplexity use over-fetch+slice
        sources = await provider_cls._search(
            config=search_config,
            query=self.query,
            max_results=effective_limit,
            offset=self.offset,
            include_raw_content=False,
        )

        sources = self._rearrange_sources(sources, starting_number=len(context.sources) + 1)

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
