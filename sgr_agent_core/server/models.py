"""OpenAI-compatible models for API endpoints."""

from datetime import datetime
from typing import Any, Literal

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field, field_validator


class ChatCompletionRequest(BaseModel):
    """Request for creating chat completion."""

    model: str | None = Field(
        default="sgr_tool_calling_agent",
        description="Agent type or existing agent identifier",
        examples=[
            "sgr_tool_calling_agent",
        ],
    )
    messages: list[ChatCompletionMessageParam] = Field(description="List of messages")
    stream: bool = Field(default=True, description="Enable streaming mode")
    max_tokens: int | None = Field(default=1500, description="Maximum number of tokens")
    temperature: float | None = Field(default=0, description="Generation temperature")

    @field_validator("messages", mode="wrap")
    @classmethod
    def validate_messages(cls, v: Any, handler: Any) -> list[dict]:
        """The ChatCompletionMessageParam is an alias for TypedDicts Union,
        if we try to validate it as is - we will fail hard"""
        if not isinstance(v, list):
            raise ValueError("messages must be a list")

        if not all(isinstance(msg, dict) for msg in v):
            raise ValueError("All messages must be dictionaries")

        return v


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
    task_messages: list[ChatCompletionMessageParam] = Field(description="Agent task messages in OpenAI format")
    state: str = Field(description="Current agent state")
    iteration: int = Field(description="Current iteration number")
    searches_used: int = Field(description="Number of searches performed")
    clarifications_used: int = Field(description="Number of clarifications requested")
    sources_count: int = Field(description="Number of sources found")
    current_step_reasoning: dict[str, Any] | None = Field(default=None, description="Current agent step")
    execution_result: str | None = Field(default=None, description="Execution result")


class AgentListItem(BaseModel):
    agent_id: str = Field(description="Agent ID")
    task_messages: list[ChatCompletionMessageParam] = Field(description="Agent task messages in OpenAI format")
    state: str = Field(description="Current agent state")
    creation_time: datetime = Field(description="Agent creation time")


class AgentListResponse(BaseModel):
    agents: list[AgentListItem] = Field(description="List of agents")
    total: int = Field(description="Total number of agents")


class ClarificationRequest(BaseModel):
    """Request for providing clarifications to an agent in OpenAI messages
    format."""

    messages: list[ChatCompletionMessageParam] = Field(description="Clarification messages in OpenAI format")
