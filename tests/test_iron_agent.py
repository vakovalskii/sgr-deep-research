"""Tests for IronAgent."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessage

from sgr_agent_core.agents.iron_agent import IronAgent
from sgr_agent_core.tools import ReasoningTool, WebSearchTool
from tests.conftest import create_test_agent


class TestIronAgent:
    """Tests for IronAgent."""

    def test_initialization(self):
        """Test IronAgent initialization."""
        agent = create_test_agent(
            IronAgent,
            task_messages=[{"role": "user", "content": "Test task"}],
            toolkit=[ReasoningTool, WebSearchTool],
        )

        assert agent.name == "iron_agent"
        assert len(agent.toolkit) == 2
        assert ReasoningTool in agent.toolkit
        assert WebSearchTool in agent.toolkit

    @pytest.mark.asyncio
    async def test_generate_tool_success(self):
        """Test _generate_tool with successful parsing."""
        agent = create_test_agent(
            IronAgent,
            toolkit=[ReasoningTool],
        )

        # Mock stream response
        mock_chunk = Mock(spec=ChatCompletionChunk)
        mock_chunk.type = "chunk"
        mock_chunk.chunk = Mock()  # Add chunk attribute

        mock_completion = Mock(spec=ChatCompletionMessage)
        mock_completion.content = (
            '{"reasoning_steps": ["step1", "step2"], "current_situation": "test", '
            '"plan_status": "ok", "enough_data": false, "remaining_steps": ["next"], '
            '"task_completed": false}'
        )

        # Create async iterator for stream
        async def async_iter():
            yield mock_chunk

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        mock_stream.__aiter__ = lambda self: async_iter()
        mock_final_completion = Mock()
        mock_final_completion.choices = [Mock(message=mock_completion)]
        mock_stream.get_final_completion = AsyncMock(return_value=mock_final_completion)

        agent.openai_client.chat.completions.stream = Mock(return_value=mock_stream)

        # Call method
        result = await agent._generate_tool(ReasoningTool, [{"role": "user", "content": "test"}])

        assert isinstance(result, ReasoningTool)
        assert result.reasoning_steps == ["step1", "step2"]

        # Check that logging was called for successful attempt
        log_entries = [entry for entry in agent.log if entry.get("step_type") == "tool_generation_attempt"]
        assert len(log_entries) == 1
        assert log_entries[0]["success"] is True
        assert log_entries[0]["tool_class"] == "ReasoningTool"
        assert log_entries[0]["llm_content"] == mock_completion.content

    @pytest.mark.asyncio
    async def test_generate_tool_retry_on_error(self):
        """Test _generate_tool with retry on parsing error."""
        agent = create_test_agent(
            IronAgent,
            toolkit=[ReasoningTool],
        )

        # Mock stream response with invalid JSON first, then valid
        mock_chunk = Mock(spec=ChatCompletionChunk)
        mock_chunk.type = "chunk"
        mock_chunk.chunk = Mock()  # Add chunk attribute

        # First attempt - invalid JSON
        mock_completion_invalid = Mock(spec=ChatCompletionMessage)
        mock_completion_invalid.content = "invalid json"

        # Second attempt - valid JSON
        mock_completion_valid = Mock(spec=ChatCompletionMessage)
        mock_completion_valid.content = (
            '{"reasoning_steps": ["step1", "step2"], "current_situation": "test", '
            '"plan_status": "ok", "enough_data": false, "remaining_steps": ["next"], '
            '"task_completed": false}'
        )

        # Create async iterator for stream
        async def async_iter():
            yield mock_chunk

        # First call returns invalid, second returns valid
        call_count = {"count": 0}

        async def get_completion():
            call_count["count"] += 1
            if call_count["count"] == 1:
                return Mock(choices=[Mock(message=mock_completion_invalid)])
            return Mock(choices=[Mock(message=mock_completion_valid)])

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        mock_stream.__aiter__ = lambda self: async_iter()
        mock_stream.get_final_completion = AsyncMock(side_effect=get_completion)

        agent.openai_client.chat.completions.stream = Mock(return_value=mock_stream)

        # Call method - should succeed on second attempt
        result = await agent._generate_tool(ReasoningTool, [{"role": "user", "content": "test"}], max_retries=5)

        assert isinstance(result, ReasoningTool)
        assert call_count["count"] == 2  # Two attempts made

        # Check that logging was called for both attempts
        # Note: due to finally block, each attempt logs twice (in except and finally)
        log_entries = [entry for entry in agent.log if entry.get("step_type") == "tool_generation_attempt"]
        # First attempt: failed (logged in except and finally)
        # Second attempt: succeeded (logged in finally)
        assert len(log_entries) >= 2
        # Find first failed attempt
        failed_entries = [e for e in log_entries if e["success"] is False and e["attempt"] == 1]
        assert len(failed_entries) >= 1
        assert failed_entries[0]["llm_content"] == "invalid json"
        # Find successful attempt
        success_entries = [e for e in log_entries if e["success"] is True and e["attempt"] == 2]
        assert len(success_entries) >= 1
        assert success_entries[0]["llm_content"] == mock_completion_valid.content

    @pytest.mark.asyncio
    async def test_prepare_tools(self):
        """Test _prepare_tools method."""
        agent = create_test_agent(
            IronAgent,
            toolkit=[ReasoningTool, WebSearchTool],
        )

        # Call _prepare_tools
        tool_selector_type = await agent._prepare_tools()

        # Check that it returns a type that is a subclass of ToolNameSelectorStub
        assert isinstance(tool_selector_type, type)
        # Check that it's a dynamically created model (has __name__)
        assert hasattr(tool_selector_type, "__name__")
        # Check that it can be instantiated with required ReasoningTool fields
        instance = tool_selector_type(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["next"],
            task_completed=False,
            function_name_choice="reasoningtool",
        )
        assert hasattr(instance, "function_name_choice")

    @pytest.mark.asyncio
    async def test_reasoning_phase(self):
        """Test _reasoning_phase."""
        agent = create_test_agent(
            IronAgent,
            toolkit=[ReasoningTool, WebSearchTool],
        )

        # Mock _generate_tool
        # The result should be a ReasoningTool with tool_name field
        from pydantic import create_model

        # Create a mock reasoning tool with function_name_choice field
        mock_reasoning_class = create_model(
            "MockReasoning",
            __base__=ReasoningTool,
            function_name_choice=(str, "websearchtool"),
        )
        mock_reasoning = mock_reasoning_class(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["next"],
            task_completed=False,
            function_name_choice="websearchtool",
        )

        agent._generate_tool = AsyncMock(return_value=mock_reasoning)

        # Call reasoning phase
        result = await agent._reasoning_phase()

        assert isinstance(result, ReasoningTool)
        assert result.reasoning_steps == ["step1", "step2"]
        assert hasattr(result, "function_name_choice")
        agent._generate_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_action_phase(self):
        """Test _select_action_phase."""
        agent = create_test_agent(
            IronAgent,
            toolkit=[ReasoningTool, WebSearchTool],
        )

        # Mock reasoning with function_name_choice field (already selected in reasoning phase)
        from pydantic import create_model

        mock_reasoning_class = create_model(
            "MockReasoning",
            __base__=ReasoningTool,
            function_name_choice=(str, "websearchtool"),
        )
        reasoning = mock_reasoning_class(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["search"],
            task_completed=False,
            function_name_choice="websearchtool",
        )

        # Mock tool instance generation
        mock_tool = WebSearchTool(reasoning="test reasoning", query="test query")
        agent._generate_tool = AsyncMock(return_value=mock_tool)

        # Call select action phase
        result = await agent._select_action_phase(reasoning)

        assert isinstance(result, WebSearchTool)
        assert result.query == "test query"
        # Only one call - tool parameter generation (tool_name already selected in reasoning)
        agent._generate_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_phase(self):
        """Test _action_phase."""

        agent = create_test_agent(
            IronAgent,
            toolkit=[WebSearchTool],
        )

        # Mock tool execution - need to patch __call__ method
        tool = WebSearchTool(reasoning="test reasoning", query="test query")

        # Patch WebSearchTool.__call__ to avoid TavilySearchService initialization
        with patch(
            "sgr_agent_core.tools.web_search_tool.WebSearchTool.__call__",
            new_callable=AsyncMock,
            return_value="Search results",
        ) as mock_call:
            # Call action phase
            result = await agent._action_phase(tool)

            assert result == "Search results"
            mock_call.assert_called_once_with(agent._context, agent.config)

    @pytest.mark.asyncio
    async def test_log_tool_generation_attempt(self):
        """Test _log_tool_instantiator logging."""
        from sgr_agent_core.services.tool_instantiator import ToolInstantiator

        agent = create_test_agent(
            IronAgent,
            toolkit=[ReasoningTool],
        )

        # Test successful attempt
        instantiator = ToolInstantiator(ReasoningTool)
        instantiator.input_content = (
            '{"reasoning_steps": ["step1", "step2"], "current_situation": "test", '
            '"plan_status": "ok", "enough_data": false, "remaining_steps": ["next"], '
            '"task_completed": false}'
        )
        instantiator.instance = ReasoningTool(
            reasoning_steps=["step1", "step2"],
            current_situation="test",
            plan_status="ok",
            enough_data=False,
            remaining_steps=["next"],
            task_completed=False,
        )

        agent._log_tool_instantiator(
            instantiator=instantiator,
            attempt=1,
            max_retries=5,
        )

        # Check log entry
        assert len(agent.log) == 1
        log_entry = agent.log[0]
        assert log_entry["step_type"] == "tool_generation_attempt"
        assert log_entry["tool_class"] == "ReasoningTool"
        assert log_entry["attempt"] == 1
        assert log_entry["max_retries"] == 5
        assert log_entry["success"] is True
        assert instantiator.instance is not None
        assert log_entry["llm_content"] == instantiator.input_content
        assert log_entry["errors"] == []

        # Test failed attempt
        instantiator2 = ToolInstantiator(ReasoningTool)
        instantiator2.input_content = "invalid json"
        instantiator2.errors = ["JSON decode error", "Validation error"]

        agent._log_tool_instantiator(
            instantiator=instantiator2,
            attempt=2,
            max_retries=5,
        )

        # Check second log entry
        assert len(agent.log) == 2
        log_entry = agent.log[1]
        assert log_entry["success"] is False
        assert log_entry["llm_content"] == "invalid json"
        assert log_entry["errors"] == ["JSON decode error", "Validation error"]
        assert instantiator2.instance is None
