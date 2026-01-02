"""Tests for API models module.

This module contains tests for OpenAI-compatible API models used in REST
endpoints.
"""

import pytest
from pydantic import ValidationError

from sgr_agent_core.server.models import (
    AgentListItem,
    AgentListResponse,
    AgentStateResponse,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ClarificationRequest,
    HealthResponse,
)


class TestChatCompletionRequest:
    """Tests for ChatCompletionRequest model."""

    def test_chat_completion_request_creation(self):
        """Test creating a chat completion request."""
        messages = [{"role": "user", "content": "Hello"}]
        request = ChatCompletionRequest(messages=messages)
        assert len(request.messages) == 1
        assert request.messages[0]["content"] == "Hello"

    def test_chat_completion_request_defaults(self):
        """Test default values for chat completion request."""
        messages = [{"role": "user", "content": "Test"}]
        request = ChatCompletionRequest(messages=messages)
        assert request.model == "sgr_tool_calling_agent"
        assert request.stream is True
        assert request.max_tokens == 1500
        assert request.temperature == 0

    def test_chat_completion_request_custom_values(self):
        """Test custom values for chat completion request."""
        messages = [{"role": "user", "content": "Test"}]
        request = ChatCompletionRequest(
            model="custom_model",
            messages=messages,
            stream=False,
            max_tokens=2000,
            temperature=0.7,
        )
        assert request.model == "custom_model"
        assert request.stream is False
        assert request.max_tokens == 2000
        assert request.temperature == 0.7

    def test_chat_completion_request_required_messages(self):
        """Test that messages field is required."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest()

    def test_chat_completion_request_multiple_messages(self):
        """Test request with multiple messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        request = ChatCompletionRequest(messages=messages)
        assert len(request.messages) == 3

    def test_chat_completion_request_multimodal_message(self):
        """Test request with multimodal message (text and image)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
                ],
            }
        ]
        request = ChatCompletionRequest(messages=messages)
        assert len(request.messages) == 1
        assert isinstance(request.messages[0]["content"], list)
        assert len(request.messages[0]["content"]) == 2

    def test_chat_completion_request_validation_list_of_dicts(self):
        """Test that messages validator accepts list of dicts."""
        messages = [{"role": "user", "content": "Test"}]
        request = ChatCompletionRequest(messages=messages)
        assert isinstance(request.messages, list)
        assert isinstance(request.messages[0], dict)

    def test_chat_completion_request_validation_rejects_non_list(self):
        """Test that messages validator rejects non-list."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages="not a list")

    def test_chat_completion_request_validation_rejects_non_dict_items(self):
        """Test that messages validator rejects non-dict items."""
        with pytest.raises(ValidationError):
            ChatCompletionRequest(messages=["not a dict"])


class TestChatCompletionResponse:
    """Tests for ChatCompletionResponse model."""

    def test_chat_completion_response_creation(self):
        """Test creating a chat completion response."""
        choice = ChatCompletionChoice(
            index=0,
            message={"role": "assistant", "content": "Response"},
            finish_reason="stop",
        )
        response = ChatCompletionResponse(
            id="chatcmpl-123",
            created=1234567890,
            model="gpt-4o",
            choices=[choice],
        )
        assert response.id == "chatcmpl-123"
        assert response.object == "chat.completion"
        assert response.created == 1234567890
        assert response.model == "gpt-4o"
        assert len(response.choices) == 1

    def test_chat_completion_response_with_usage(self):
        """Test response with usage information."""
        choice = ChatCompletionChoice(
            index=0,
            message={"role": "assistant", "content": "Response"},
            finish_reason="stop",
        )
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        response = ChatCompletionResponse(
            id="chatcmpl-123",
            created=1234567890,
            model="gpt-4o",
            choices=[choice],
            usage=usage,
        )
        assert response.usage == usage
        assert response.usage["total_tokens"] == 30

    def test_chat_completion_choice_structure(self):
        """Test ChatCompletionChoice structure."""
        message = {"role": "assistant", "content": "Test response"}
        choice = ChatCompletionChoice(
            index=0,
            message=message,
            finish_reason="stop",
        )
        assert choice.index == 0
        assert choice.message["role"] == "assistant"
        assert choice.message["content"] == "Test response"
        assert choice.finish_reason == "stop"


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response_creation(self):
        """Test creating a health response."""
        response = HealthResponse()
        assert response.status == "healthy"
        assert response.service == "SGR Agent Core API"

    def test_health_response_custom_service(self):
        """Test health response with custom service name."""
        response = HealthResponse(service="Custom Service")
        assert response.status == "healthy"
        assert response.service == "Custom Service"


class TestAgentStateResponse:
    """Tests for AgentStateResponse model."""

    def test_agent_state_response_creation(self):
        """Test creating an agent state response."""
        response = AgentStateResponse(
            agent_id="agent_123",
            task_messages=[{"role": "user", "content": "Research task"}],
            state="researching",
            iteration=5,
            searches_used=3,
            clarifications_used=1,
            sources_count=10,
        )
        assert response.agent_id == "agent_123"
        assert len(response.task_messages) == 1
        assert response.task_messages[0]["content"] == "Research task"
        assert response.state == "researching"
        assert response.iteration == 5
        assert response.searches_used == 3
        assert response.clarifications_used == 1
        assert response.sources_count == 10

    def test_agent_state_response_with_optional_fields(self):
        """Test agent state response with optional fields."""
        response = AgentStateResponse(
            agent_id="agent_123",
            task_messages=[{"role": "user", "content": "Research task"}],
            state="completed",
            iteration=10,
            searches_used=5,
            clarifications_used=2,
            sources_count=15,
            current_step_reasoning={"step": "final"},
            execution_result="Task completed successfully",
        )
        assert response.current_step_reasoning == {"step": "final"}
        assert response.execution_result == "Task completed successfully"

    def test_agent_state_response_defaults_none(self):
        """Test that optional fields default to None."""
        response = AgentStateResponse(
            agent_id="agent_123",
            task_messages=[{"role": "user", "content": "Test"}],
            state="inited",
            iteration=0,
            searches_used=0,
            clarifications_used=0,
            sources_count=0,
        )
        assert response.current_step_reasoning is None
        assert response.execution_result is None

    def test_agent_state_response_multiple_messages(self):
        """Test agent state response with multiple task messages."""
        response = AgentStateResponse(
            agent_id="agent_123",
            task_messages=[
                {"role": "system", "content": "You are a researcher"},
                {"role": "user", "content": "Research quantum computing"},
            ],
            state="researching",
            iteration=1,
            searches_used=0,
            clarifications_used=0,
            sources_count=0,
        )
        assert len(response.task_messages) == 2
        assert response.task_messages[0]["role"] == "system"
        assert response.task_messages[1]["role"] == "user"


class TestAgentListItem:
    """Tests for AgentListItem model."""

    def test_agent_list_item_creation(self):
        """Test creating an agent list item."""
        from datetime import datetime

        now = datetime.now()
        item = AgentListItem(
            agent_id="agent_123",
            task_messages=[{"role": "user", "content": "Research quantum computing"}],
            state="researching",
            creation_time=now,
        )
        assert item.agent_id == "agent_123"
        assert len(item.task_messages) == 1
        assert item.task_messages[0]["content"] == "Research quantum computing"
        assert item.state == "researching"
        assert item.creation_time == now

    def test_agent_list_item_required_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            AgentListItem(agent_id="agent_123", task_messages=[{"role": "user", "content": "Test"}])


class TestAgentListResponse:
    """Tests for AgentListResponse model."""

    def test_agent_list_response_creation(self):
        """Test creating an agent list response."""
        from datetime import datetime

        now = datetime.now()
        items = [
            AgentListItem(
                agent_id="agent_1",
                task_messages=[{"role": "user", "content": "Task 1"}],
                state="completed",
                creation_time=now,
            ),
            AgentListItem(
                agent_id="agent_2",
                task_messages=[{"role": "user", "content": "Task 2"}],
                state="researching",
                creation_time=now,
            ),
        ]
        response = AgentListResponse(agents=items, total=2)
        assert len(response.agents) == 2
        assert response.total == 2

    def test_agent_list_response_empty(self):
        """Test agent list response with no agents."""
        response = AgentListResponse(agents=[], total=0)
        assert len(response.agents) == 0
        assert response.total == 0

    def test_agent_list_response_total_mismatch(self):
        """Test that total can differ from agents length (pagination)."""
        from datetime import datetime

        now = datetime.now()
        items = [
            AgentListItem(
                agent_id="agent_1",
                task_messages=[{"role": "user", "content": "Task 1"}],
                state="completed",
                creation_time=now,
            )
        ]
        # Total can be higher (e.g., pagination showing 1 of 10)
        response = AgentListResponse(agents=items, total=10)
        assert len(response.agents) == 1
        assert response.total == 10


class TestClarificationRequest:
    """Tests for ClarificationRequest model."""

    def test_clarification_request_creation(self):
        """Test creating a clarification request."""
        content = "Here are my answers: 1. Yes 2. No 3. Maybe"
        request = ClarificationRequest(messages=[{"role": "user", "content": content}])
        assert len(request.messages) == 1
        assert request.messages[0]["content"] == content

    def test_clarification_request_required_field(self):
        """Test that messages field is required."""
        with pytest.raises(ValidationError):
            ClarificationRequest()

    def test_clarification_request_empty_list(self):
        """Test clarification request with empty list."""
        request = ClarificationRequest(messages=[])
        assert request.messages == []

    def test_clarification_request_multiple_messages(self):
        """Test clarification request with multiple messages."""
        request = ClarificationRequest(
            messages=[
                {"role": "user", "content": "Answer 1: Yes"},
                {"role": "user", "content": "Answer 2: No"},
            ]
        )
        assert len(request.messages) == 2
        assert request.messages[0]["content"] == "Answer 1: Yes"
        assert request.messages[1]["content"] == "Answer 2: No"

    def test_clarification_request_with_system_message(self):
        """Test clarification request with system message."""
        request = ClarificationRequest(
            messages=[
                {"role": "system", "content": "Context for clarification"},
                {"role": "user", "content": "My clarification"},
            ]
        )
        assert len(request.messages) == 2
        assert request.messages[0]["role"] == "system"
        assert request.messages[1]["role"] == "user"
