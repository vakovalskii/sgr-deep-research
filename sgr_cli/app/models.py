"""Data models for SGR CLI."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """Chat message model."""

    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_arguments: Optional[dict[str, Any]] = None
    tool_result: Optional[str] = None
    images: list[str] = Field(default_factory=list, description="Image paths or URLs")
    clarification_questions: Optional[list[str]] = None


class ToolExecution(BaseModel):
    """Tool execution record."""

    tool_name: str
    arguments: dict[str, Any]
    result: str
    timestamp: datetime = Field(default_factory=datetime.now)
    iteration: int
    status: str = "completed"  # completed, failed, pending


class AgentState(str, Enum):
    """Agent execution state."""

    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"
