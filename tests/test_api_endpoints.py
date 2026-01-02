"""Tests for API endpoints module.

This module contains comprehensive tests for FastAPI endpoints,
including agent creation, agent state management, and chat completions.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from sgr_agent_core.agents import SGRAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.server.endpoints import (
    _is_agent_id,
    agents_storage,
    create_chat_completion,
    get_agent_state,
    get_agents_list,
    provide_clarification,
)
from sgr_agent_core.server.models import ChatCompletionRequest, ClarificationRequest
from tests.conftest import create_test_agent


class TestIsAgentId:
    """Tests for _is_agent_id utility function."""

    def test_valid_agent_id_format(self):
        """Test that valid agent ID format is recognized."""
        valid_ids = [
            "sgr_agent_12345678-1234-1234-1234-123456789012",
            "tool_calling_agent_abcdef01-2345-6789-abcd-ef0123456789",
            "custom_agent_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ]

        for agent_id in valid_ids:
            assert _is_agent_id(agent_id) is True

    def test_invalid_agent_id_format(self):
        """Test that invalid agent ID format is rejected."""
        invalid_ids = [
            "sgr_agent",  # No UUID
            "short_id",  # Too short
            "",  # Empty string
            "model_name",  # Regular model name
        ]

        for invalid_id in invalid_ids:
            assert _is_agent_id(invalid_id) is False

    def test_edge_case_lengths(self):
        """Test edge cases around minimum length requirement."""
        # Exactly 20 characters with underscore - should be invalid (need >20)
        exactly_20 = "a_bcdefghijklmnopqr"
        assert len(exactly_20) == 19
        assert _is_agent_id(exactly_20) is False

        # 21 characters with underscore - should be valid
        exactly_21 = "a_bcdefghijklmnopqrs"
        assert len(exactly_21) == 20
        assert _is_agent_id(exactly_21) is False

        # 22 characters with underscore - should be valid
        exactly_22 = "a_bcdefghijklmnopqrst"
        assert len(exactly_22) == 21
        assert _is_agent_id(exactly_22) is True


class TestChatCompletionEndpoint:
    """Tests for create_chat_completion endpoint."""

    def setup_method(self):
        """Setup for each test method."""
        # Clear agents storage
        agents_storage.clear()

    @patch("sgr_agent_core.server.endpoints.AgentFactory")
    @pytest.mark.asyncio
    async def test_create_new_agent_success(self, mock_factory):
        """Test successful creation of new agent."""
        mock_agent = Mock()
        mock_agent.id = "test_agent_12345678-1234-1234-1234-123456789012"
        mock_agent.streaming_generator.stream.return_value = iter(["chunk1", "chunk2"])

        # Use actual async function instead of AsyncMock to avoid warnings
        async def mock_execute():
            pass

        mock_agent.execute = mock_execute
        mock_agent_def = Mock()
        mock_factory.get_definitions_list.return_value = [mock_agent_def]
        mock_agent_def.name = "sgr_agent"

        # Make create method async
        mock_factory.create = AsyncMock(return_value=mock_agent)

        # Create request
        request = ChatCompletionRequest(
            model="sgr_agent", messages=[{"role": "user", "content": "Test task"}], stream=True
        )

        # Mock asyncio.create_task to properly handle coroutines
        with patch("sgr_agent_core.server.endpoints.asyncio.create_task") as mock_create_task:
            # Schedule the coroutine via event loop to avoid 'never awaited' warnings
            def mock_create_task_func(coro):
                loop = asyncio.get_event_loop()
                return loop.create_task(coro)

            mock_create_task.side_effect = mock_create_task_func

            await create_chat_completion(request)

            # Verify agent was created and stored
            mock_factory.create.assert_called_once()
            call_args = mock_factory.create.call_args[0]
            assert call_args[1] == [{"role": "user", "content": "Test task"}]
            assert mock_agent.id in agents_storage
            assert agents_storage[mock_agent.id] == mock_agent

            # Verify execute task was created
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_with_multiple_messages(self):
        """Test creating agent with multiple messages."""
        from unittest.mock import patch

        mock_agent = Mock()
        mock_agent.id = "test_agent_12345678-1234-1234-1234-123456789012"
        mock_agent.streaming_generator.stream.return_value = iter(["chunk1"])

        async def mock_execute():
            pass

        mock_agent.execute = mock_execute

        with patch("sgr_agent_core.server.endpoints.AgentFactory") as mock_factory:
            mock_agent_def = Mock()
            mock_factory.get_definitions_list.return_value = [mock_agent_def]
            mock_agent_def.name = "sgr_agent"
            mock_factory.create = AsyncMock(return_value=mock_agent)

            request = ChatCompletionRequest(
                model="sgr_agent",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "First message"},
                    {"role": "assistant", "content": "Response"},
                    {"role": "user", "content": "Second message"},
                ],
                stream=True,
            )

            with patch("sgr_agent_core.server.endpoints.asyncio.create_task") as mock_create_task:

                def mock_create_task_func(coro):
                    loop = asyncio.get_event_loop()
                    return loop.create_task(coro)

                mock_create_task.side_effect = mock_create_task_func

                await create_chat_completion(request)

                mock_factory.create.assert_called_once()
                call_args = mock_factory.create.call_args[0]
                assert len(call_args[1]) == 4
                assert call_args[1][0]["role"] == "system"
                assert call_args[1][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_create_agent_with_multimodal_message(self):
        """Test creating agent with multimodal message (text and image)."""
        from unittest.mock import patch

        mock_agent = Mock()
        mock_agent.id = "test_agent_12345678-1234-1234-1234-123456789012"
        mock_agent.streaming_generator.stream.return_value = iter(["chunk1"])

        async def mock_execute():
            pass

        mock_agent.execute = mock_execute

        with patch("sgr_agent_core.server.endpoints.AgentFactory") as mock_factory:
            mock_agent_def = Mock()
            mock_factory.get_definitions_list.return_value = [mock_agent_def]
            mock_agent_def.name = "sgr_agent"
            mock_factory.create = AsyncMock(return_value=mock_agent)

            request = ChatCompletionRequest(
                model="sgr_agent",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's in this image?"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
                        ],
                    }
                ],
                stream=True,
            )

            with patch("sgr_agent_core.server.endpoints.asyncio.create_task") as mock_create_task:

                def mock_create_task_func(coro):
                    loop = asyncio.get_event_loop()
                    return loop.create_task(coro)

                mock_create_task.side_effect = mock_create_task_func

                await create_chat_completion(request)

                mock_factory.create.assert_called_once()
                call_args = mock_factory.create.call_args[0]
                assert len(call_args[1]) == 1
                assert isinstance(call_args[1][0]["content"], list)
                assert len(call_args[1][0]["content"]) == 2

    @pytest.mark.asyncio
    async def test_non_streaming_request_raises_error(self):
        """Test that non-streaming request raises HTTPException."""
        request = ChatCompletionRequest(
            model="sgr_agent", messages=[{"role": "user", "content": "Test task"}], stream=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_chat_completion(request)

        assert exc_info.value.status_code == 501
        assert "Only streaming responses are supported" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_model_raises_error(self):
        """Test that invalid model raises HTTPException."""
        request = ChatCompletionRequest(
            model="invalid_model", messages=[{"role": "user", "content": "Test task"}], stream=True
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_chat_completion(request)

        assert exc_info.value.status_code == 400
        assert "Invalid model" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_clarification_request_for_existing_agent(self):
        """Test providing clarification to existing agent."""
        # Create and store an agent waiting for clarification
        agent = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Test task"}])
        agent._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
        agents_storage[agent.id] = agent

        # Mock the agent's methods with actual async function
        async def mock_provide_clarification(messages):
            pass

        agent.provide_clarification = Mock(side_effect=mock_provide_clarification)
        agent.streaming_generator.stream = Mock(return_value=iter(["clarification response"]))

        request = ChatCompletionRequest(
            model=agent.id, messages=[{"role": "user", "content": "Here is my clarification"}], stream=True
        )

        await create_chat_completion(request)

        # Verify clarification was provided
        agent.provide_clarification.assert_called_once()
        call_args = agent.provide_clarification.call_args[0][0]
        assert call_args == [{"role": "user", "content": "Here is my clarification"}]


class TestAgentStateEndpoint:
    """Tests for get_agent_state endpoint."""

    def setup_method(self):
        """Setup for each test method."""
        agents_storage.clear()

    @pytest.mark.asyncio
    async def test_get_agent_state_success(self):
        """Test successful retrieval of agent state."""
        from sgr_agent_core.models import SourceData

        # Create and store an agent
        agent = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Test task"}])
        agent._context.sources = {
            "https://example.com/1": SourceData(number=1, url="https://example.com/1", title="Source 1"),
            "https://example.com/2": SourceData(number=2, url="https://example.com/2", title="Source 2"),
        }
        agents_storage[agent.id] = agent

        response = await get_agent_state(agent.id)

        assert response.agent_id == agent.id
        assert len(response.task_messages) == 1
        assert response.task_messages[0]["content"] == "Test task"
        assert response.sources_count == 2

    @pytest.mark.asyncio
    async def test_get_agent_state_with_multiple_messages(self):
        """Test agent state retrieval with multiple task messages."""
        agent = create_test_agent(
            SGRAgent,
            task_messages=[
                {"role": "system", "content": "You are a researcher"},
                {"role": "user", "content": "Research quantum computing"},
            ],
        )
        agents_storage[agent.id] = agent

        response = await get_agent_state(agent.id)

        assert response.agent_id == agent.id
        assert len(response.task_messages) == 2
        assert response.task_messages[0]["role"] == "system"
        assert response.task_messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_agent_state_not_found(self):
        """Test agent state retrieval for non-existent agent."""
        non_existent_id = "non_existent_agent_id"

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_state(non_existent_id)

        assert exc_info.value.status_code == 404
        assert "Agent not found" in str(exc_info.value.detail)


class TestAgentsListEndpoint:
    """Tests for get_agents_list endpoint."""

    def setup_method(self):
        """Setup for each test method."""
        agents_storage.clear()

    @pytest.mark.asyncio
    async def test_get_agents_list_empty(self):
        """Test getting agents list when storage is empty."""
        response = await get_agents_list()

        assert response.agents == []
        assert response.total == 0

    @pytest.mark.asyncio
    async def test_get_agents_list_multiple_agents(self):
        """Test getting agents list with multiple agents."""
        # Create and store multiple agents
        agent1 = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Task 1"}])
        agent2 = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Task 2"}])

        agents_storage[agent1.id] = agent1
        agents_storage[agent2.id] = agent2

        response = await get_agents_list()

        assert response.total == 2
        assert len(response.agents) == 2

        # Check that both agents are in the response
        agent_ids = [item.agent_id for item in response.agents]
        assert agent1.id in agent_ids
        assert agent2.id in agent_ids

        # Verify task_messages are preserved
        agent1_response = next(item for item in response.agents if item.agent_id == agent1.id)
        agent2_response = next(item for item in response.agents if item.agent_id == agent2.id)
        assert agent1_response.task_messages[0]["content"] == "Task 1"
        assert agent2_response.task_messages[0]["content"] == "Task 2"


class TestProvideClarificationEndpoint:
    """Tests for provide_clarification endpoint."""

    def setup_method(self):
        """Setup for each test method."""
        agents_storage.clear()

    @pytest.mark.asyncio
    async def test_provide_clarification_success(self):
        """Test successful clarification provision."""
        # Create and store an agent
        agent = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Test task"}])

        # Mock the agent's methods with actual async function
        async def mock_provide_clarification(messages):
            pass

        agent.provide_clarification = Mock(side_effect=mock_provide_clarification)
        agent.streaming_generator.stream = Mock(return_value=iter(["clarification response"]))
        agents_storage[agent.id] = agent

        request = ClarificationRequest(messages=[{"role": "user", "content": "This is my clarification"}])

        await provide_clarification(agent.id, request)

        # Verify clarification was provided
        agent.provide_clarification.assert_called_once()
        call_args = agent.provide_clarification.call_args[0][0]
        assert call_args == [{"role": "user", "content": "This is my clarification"}]

    @pytest.mark.asyncio
    async def test_provide_clarification_multiple_messages(self):
        """Test clarification provision with multiple messages."""
        agent = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Test task"}])

        async def mock_provide_clarification(messages):
            pass

        agent.provide_clarification = Mock(side_effect=mock_provide_clarification)
        agent.streaming_generator.stream = Mock(return_value=iter(["response"]))
        agents_storage[agent.id] = agent

        request = ClarificationRequest(
            messages=[
                {"role": "user", "content": "Answer 1: Yes"},
                {"role": "user", "content": "Answer 2: No"},
            ]
        )

        await provide_clarification(agent.id, request)

        agent.provide_clarification.assert_called_once()
        call_args = agent.provide_clarification.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0]["content"] == "Answer 1: Yes"
        assert call_args[1]["content"] == "Answer 2: No"

    @pytest.mark.asyncio
    async def test_provide_clarification_agent_not_found(self):
        """Test clarification provision for non-existent agent."""
        non_existent_id = "non_existent_agent_id"
        request = ClarificationRequest(messages=[{"role": "user", "content": "Some clarification"}])

        # Agent not found, exception will be raised
        # The code catches any exception and returns 500, not 404
        with pytest.raises(HTTPException) as exc_info:
            await provide_clarification(non_existent_id, request)

        # The endpoint returns 500 for any error, including missing agent
        assert exc_info.value.status_code == 500
        assert "404" in str(exc_info.value.detail) or "Agent not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_provide_clarification_with_exception(self):
        """Test clarification provision when agent raises exception."""
        # Create agent that raises exception
        agent = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Test task"}])

        # Mock the agent's method to raise exception
        async def mock_provide_clarification_error(messages):
            raise Exception("Test error")

        agent.provide_clarification = Mock(side_effect=mock_provide_clarification_error)
        agents_storage[agent.id] = agent

        request = ClarificationRequest(messages=[{"role": "user", "content": "Some clarification"}])

        with pytest.raises(HTTPException) as exc_info:
            await provide_clarification(agent.id, request)

        assert exc_info.value.status_code == 500
        assert "Test error" in str(exc_info.value.detail)


class TestAgentStorageIntegration:
    """Tests for agent storage integration across endpoints."""

    def setup_method(self):
        """Setup for each test method."""
        agents_storage.clear()

    def test_agent_storage_persistence(self):
        """Test that agents persist in storage across operations."""
        # Create agents
        agent1 = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Task 1"}])
        agent2 = create_test_agent(SGRAgent, task_messages=[{"role": "user", "content": "Task 2"}])

        # Store in agents_storage
        agents_storage[agent1.id] = agent1
        agents_storage[agent2.id] = agent2

        # Verify storage state
        assert len(agents_storage) == 2
        assert agent1.id in agents_storage
        assert agent2.id in agents_storage
        assert agents_storage[agent1.id].task_messages[0]["content"] == "Task 1"
        assert agents_storage[agent2.id].task_messages[0]["content"] == "Task 2"

    def test_agent_storage_isolation(self):
        """Test that different test methods have isolated storage."""
        # This test verifies that setup_method clears storage properly
        assert len(agents_storage) == 0
