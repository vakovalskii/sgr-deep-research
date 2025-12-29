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


class AgentContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    current_step_reasoning: Any = None
    execution_result: str | None = None

    state: AgentStatesEnum = Field(default=AgentStatesEnum.INITED, description="Current research state")
    iteration: int = Field(default=0, description="Current iteration number")

    searches: list[SearchResult] = Field(default_factory=list, description="List of performed searches")
    sources: dict[str, SourceData] = Field(default_factory=dict, description="Dictionary of found sources")

    searches_used: int = Field(default=0, description="Number of searches performed")

    clarifications_used: int = Field(default=0, description="Number of clarifications requested")
    clarification_received: asyncio.Event = Field(
        default_factory=asyncio.Event, description="Event for clarification synchronization"
    )

    custom_context: dict | BaseModel | None = Field(
        default=None, description="Custom context for project-specific data"
    )

    def agent_state(self) -> dict:
        return self.model_dump(exclude={"searches", "sources", "clarification_received"})


class AgentStatistics(BaseModel):
    pass
