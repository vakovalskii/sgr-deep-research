import asyncio
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from sgr_agent_core.skills.models import BaseSkill


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
    CANCELLED = "cancelled"

    FINISH_STATES = {COMPLETED, FAILED, ERROR, CANCELLED}


# Context fields that cannot (or must not) be serialized into a checkpoint: the
# clarification event is a live asyncio primitive, and skills are re-resolved
# from configuration when the agent is rebuilt.
_CONTEXT_SNAPSHOT_EXCLUDE = {"clarification_received", "available_skills"}


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

    available_skills: list[BaseSkill] = Field(
        default_factory=list, description="Skills available to the agent this run"
    )

    def agent_state(self) -> dict:
        return self.model_dump(exclude={"searches", "sources", "clarification_received", "available_skills"})

    def to_snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of the restorable state.

        Excludes runtime-only fields (the clarification event and the
        resolved skills) so the result can be persisted to disk and
        rebuilt later via :meth:`from_snapshot`.
        """
        return self.model_dump(mode="json", exclude=_CONTEXT_SNAPSHOT_EXCLUDE)

    @classmethod
    def from_snapshot(cls, data: dict, available_skills: list[BaseSkill] | None = None) -> "AgentContext":
        """Rebuild a context from a snapshot produced by :meth:`to_snapshot`.

        A fresh clarification event is created automatically (via the
        field default factory); skills are injected from the caller
        since they are re-resolved from configuration on restore.
        """
        payload = {k: v for k, v in data.items() if k not in _CONTEXT_SNAPSHOT_EXCLUDE}
        payload["available_skills"] = available_skills or []
        return cls.model_validate(payload)


class AgentCheckpoint(BaseModel):
    """A restorable snapshot of an agent taken at a given execution step."""

    model_config = {"arbitrary_types_allowed": True}

    agent_id: str = Field(description="Id of the agent the checkpoint belongs to")
    def_name: str | None = Field(default=None, description="Agent definition name used to rebuild the agent")
    step: int = Field(description="Execution iteration this checkpoint captures")
    created_at: datetime = Field(default_factory=datetime.now, description="Checkpoint creation timestamp")
    session_id: str | None = Field(default=None, description="Optional external session id (e.g. ACP session)")
    task_messages: list[dict] = Field(default_factory=list, description="Original task messages")
    conversation: list[dict] = Field(default_factory=list, description="Agent conversation snapshot")
    context: dict = Field(default_factory=dict, description="AgentContext snapshot (see AgentContext.to_snapshot)")


class AgentStatistics(BaseModel):
    pass
