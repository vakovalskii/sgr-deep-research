"""OpenAI-compatible models for API endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Union

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field


class ChatCompletionRequest(BaseModel):
    """Request for creating chat completion."""

    model: str | None = Field(
        default="sgr_tool_calling_agent",
        description="Agent type or existing agent identifier",
        examples=[
            "sgr_tool_calling_agent",
        ],
    )
    messages: List[ChatCompletionMessageParam] = Field(description="List of messages")
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
    choices: List[ChatCompletionChoice] = Field(description="List of choices")
    usage: Dict[str, int] | None = Field(default=None, description="Usage information")


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: str = Field(default="SGR Agent Core API", description="Service name")


class AgentStateResponse(BaseModel):
    agent_id: str = Field(description="Agent ID")
    task: str = Field(description="Agent task")
    user_context: list[ChatCompletionMessageParam] | None = Field(default=None, description="User Context with task")
    state: str = Field(description="Current agent state")
    iteration: int = Field(description="Current iteration number")
    searches_used: int = Field(description="Number of searches performed")
    clarifications_used: int = Field(description="Number of clarifications requested")
    sources_count: int = Field(description="Number of sources found")
    current_step_reasoning: Dict[str, Any] | None = Field(default=None, description="Current agent step")
    execution_result: str | None = Field(default=None, description="Execution result")


class AgentListItem(BaseModel):
    agent_id: str = Field(description="Agent ID")
    task: str = Field(description="Agent task")
    state: str = Field(description="Current agent state")
    creation_time: datetime = Field(description="Agent creation time")


class AgentListResponse(BaseModel):
    agents: List[AgentListItem] = Field(description="List of agents")
    total: int = Field(description="Total number of agents")


class ClarificationRequest(BaseModel):
    """Simple request for providing clarifications to an agent."""

    clarifications: Union[str, List[Dict[str, Any]]] = Field(
        description="Clarification content: text string or OpenAI content parts (text/image_url)"
    )
