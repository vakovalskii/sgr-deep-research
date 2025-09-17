import asyncio
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceData(BaseModel):
    """Data about a research source."""

    number: int = Field(description="Citation number")
    title: str | None = Field(default="Untitled", description="Page title")
    url: str = Field(description="Source URL")
    snippet: str = Field(default="", description="Search snippet or summary")
    full_content: str = Field(default="", description="Full scraped content")
    char_count: int = Field(default=0, description="Character count of full content")

    def __str__(self):
        return f"[{self.number}] {self.title or 'Untitled'} - {self.url}"


class SearchResult(BaseModel):
    """Search result with query, answer, and sources."""

    query: str = Field(description="Search query")
    answer: str | None = Field(default=None, description="AI-generated answer from search")
    citations: list[SourceData] = Field(default_factory=list, description="List of source citations")
    timestamp: datetime = Field(default_factory=datetime.now, description="Search execution timestamp")

    def __str__(self):
        return f"Search: '{self.query}' ({len(self.citations)} sources)"


class AgentStatesEnum(str, Enum):
    INITED = "inited"
    RESEARCHING = "researching"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    COMPLETED = "completed"
    ERROR = "error"
    FAILED = "failed"

    FINISH_STATES = {COMPLETED, FAILED, ERROR}


class ResearchContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    current_state_reasoning: Any = None

    state: AgentStatesEnum = Field(default=AgentStatesEnum.INITED, description="Current research state")
    iteration: int = Field(default=0, description="Current iteration number")

    searches: list[SearchResult] = Field(default_factory=list, description="List of performed searches")
    sources: dict[str, SourceData] = Field(default_factory=dict, description="Dictionary of found sources")
    previous_searches_summary: str = Field(default="", description="Summary of previous searches to maintain context")

    searches_used: int = Field(default=0, description="Number of searches performed")
    
    report_created: bool = Field(default=False, description="Whether research report has been created")

    clarifications_used: int = Field(default=0, description="Number of clarifications requested")
    clarification_received: asyncio.Event = Field(
        default_factory=asyncio.Event, description="Event for clarification synchronization"
    )

    # ToDO: rename, my creativity finished now
    def agent_state(self) -> dict:
        return self.model_dump(exclude={"searches", "sources", "clarification_received"})
    
    def cleanup_old_searches_and_save_summary(self, max_searches_to_keep: int = 1) -> None:
        """Clean up old search results and save summary to prevent context overflow."""
        if len(self.searches) > max_searches_to_keep:
            # Create summary of searches that will be removed
            old_searches = self.searches[:-max_searches_to_keep]
            summary_parts = []
            
            for search in old_searches:
                search_summary = f"Query: '{search.query}'"
                if search.answer:
                    search_summary += f" - Answer: {search.answer[:200]}..."
                if search.citations:
                    key_sources = [f"{cite.title} ({cite.url})" for cite in search.citations[:2]]
                    search_summary += f" - Sources: {', '.join(key_sources)}"
                summary_parts.append(search_summary)
            
            # Update summary
            new_summary = "\n".join(summary_parts)
            if self.previous_searches_summary:
                self.previous_searches_summary += f"\n\n--- Previous searches ---\n{new_summary}"
            else:
                self.previous_searches_summary = new_summary
            
            # Keep only recent searches
            self.searches = self.searches[-max_searches_to_keep:]
            
            # Clean up old sources (keep only sources referenced in recent searches)
            recent_source_urls = set()
            for search in self.searches:
                for cite in search.citations:
                    recent_source_urls.add(cite.url)
            
            # Remove old sources
            self.sources = {url: source for url, source in self.sources.items() 
                          if url in recent_source_urls}


class AgentStatistics(BaseModel):
    pass
