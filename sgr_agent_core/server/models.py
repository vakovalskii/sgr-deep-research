"""OpenAI-compatible models for API endpoints."""

from copy import deepcopy
from datetime import datetime
from typing import Any, ClassVar, Literal

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field, RootModel, computed_field, field_serializer, field_validator

from sgr_agent_core.utils import _AGENT_ID_SEARCH_RE


class MessagesList(RootModel[list[ChatCompletionMessageParam]]):
    """Root model for list of chat completion messages."""

    MAX_BASE64_LENGTH: ClassVar[int] = 200

    root: list[ChatCompletionMessageParam] = Field(description="List of messages")

    @field_validator("root", mode="wrap")
    @classmethod
    def validate_messages(cls, v: Any, handler: Any) -> list[dict]:
        """The ChatCompletionMessageParam is an alias for TypedDicts Union,
        if we try to validate it as is - we will fail hard"""
        if not isinstance(v, list):
            raise ValueError("messages must be a list")

        if not all(isinstance(msg, dict) for msg in v):
            raise ValueError("All messages must be dictionaries")

        return v

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: int) -> ChatCompletionMessageParam:
        return self.root[index]

    def __iter__(self):
        return iter(self.root)

    @field_serializer("root", mode="wrap")
    def serialize_root(self, value, serializer, info):
        """Serialize the root field with truncated base64 image URLs."""
        truncated_messages = deepcopy(value)

        for msg in truncated_messages:
            try:
                for entry in msg["content"]:
                    if entry["type"] == "image_url":
                        url = entry["image_url"]["url"]
                        # Only truncate if length exceeds the limit
                        if len(url) > self.MAX_BASE64_LENGTH:
                            entry["image_url"]["url"] = url[: self.MAX_BASE64_LENGTH] + "...[truncated]"
            except (KeyError, IndexError, TypeError):
                pass
        return truncated_messages


class MessagesRequest(BaseModel):
    """Request body with messages only.

    Used for provide_clarification; ChatCompletionRequest extends it.
    """

    messages: MessagesList = Field(description="List of messages in OpenAI format")

    @computed_field
    @property
    def agent_id_from_messages(self) -> str | None:
        """Extract agent ID from messages if present.

        Looks for the 'agent {id} started' marker that the agent emits
        at the beginning of its execution, or any other text that
        matches the name_uuid format. Returns the first match or None.
        """
        for msg in self.messages:
            try:
                content = msg["content"]
                try:
                    texts = [p["text"] for p in content if p.get("type") == "text"]
                except (TypeError, AttributeError):
                    texts = [content]
                for text in texts:
                    match = _AGENT_ID_SEARCH_RE.search(text)
                    if match:
                        return match.group(1)
            except (KeyError, TypeError):
                continue
        return None


class ChatCompletionRequest(MessagesRequest):
    """Request for creating chat completion.

    Extends MessagesRequest with model, stream, etc.
    """

    model: str | None = Field(
        default="sgr_tool_calling_agent",
        description="Agent type or existing agent identifier",
        examples=[
            "sgr_tool_calling_agent",
        ],
    )
    stream: bool = Field(default=True, description="Enable streaming mode")
    max_tokens: int | None = Field(default=1500, description="Maximum number of tokens")
    temperature: float | None = Field(default=0, description="Generation temperature")


class ChatCompletionChoice(BaseModel):
    """Choice in chat completion response."""

    index: int = Field(description="Choice index")
    message: ChatCompletionMessageParam = Field(description="Response message")
    finish_reason: str | None = Field(description="Finish reason")


class ChatCompletionResponse(BaseModel):
    """Chat completion response (non-streaming)."""

    id: str = Field(description="Response ID")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(description="Creation time")
    model: str = Field(description="Model used")
    choices: list[ChatCompletionChoice] = Field(description="List of choices")
    usage: dict[str, int] | None = Field(default=None, description="Usage information")


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: str = Field(default="SGR Agent Core API", description="Service name")


class AgentStateResponse(BaseModel):
    agent_id: str = Field(description="Agent ID")
    task_messages: MessagesList = Field(description="Agent task messages in OpenAI format")
    state: str = Field(description="Current agent state")
    iteration: int = Field(description="Current iteration number")
    searches_used: int = Field(description="Number of searches performed")
    clarifications_used: int = Field(description="Number of clarifications requested")
    sources_count: int = Field(description="Number of sources found")
    current_step_reasoning: dict[str, Any] | None = Field(default=None, description="Current agent step")
    execution_result: str | None = Field(default=None, description="Execution result")


class AgentListItem(BaseModel):
    agent_id: str = Field(description="Agent ID")
    task_messages: MessagesList = Field(description="Agent task messages in OpenAI format")
    state: str = Field(description="Current agent state")
    creation_time: datetime = Field(description="Agent creation time")


class AgentListResponse(BaseModel):
    agents: list[AgentListItem] = Field(description="List of agents")
    total: int = Field(description="Total number of agents")


class AgentCancelResponse(BaseModel):
    """Response for cancelling an agent."""

    agent_id: str = Field(description="Agent ID that was cancelled")
    cancelled: bool = Field(description="Whether the agent was successfully cancelled")
    state: str = Field(description="Current state of the agent after cancellation")


class AgentDeleteResponse(BaseModel):
    """Response for deleting (cancelling) an agent."""

    agent_id: str = Field(description="Agent ID that was deleted")
    deleted: bool = Field(description="Whether the agent was successfully deleted")
    final_state: str = Field(description="Final state of the agent after deletion")
