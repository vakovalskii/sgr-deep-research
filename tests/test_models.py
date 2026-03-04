"""Tests for core models module.

This module contains tests for data models used in the SGR Deep Research
system.
"""

import asyncio
from datetime import datetime

import pytest
from pydantic import ValidationError

from sgr_agent_core.models import AgentContext, AgentStatesEnum, SearchResult, SourceData


class TestSourceData:
    """Tests for SourceData model."""

    def test_source_data_creation(self):
        """Test creating a source data with valid data."""
        source = SourceData(
            number=1,
            title="Test Article",
            url="https://example.com/article",
            snippet="This is a test snippet",
            full_content="This is the full content of the article",
            char_count=100,
        )
        assert source.number == 1
        assert source.title == "Test Article"
        assert source.url == "https://example.com/article"
        assert source.snippet == "This is a test snippet"
        assert source.full_content == "This is the full content of the article"
        assert source.char_count == 100

    def test_source_data_with_defaults(self):
        """Test creating a source data with default values."""
        source = SourceData(number=1, url="https://example.com")
        assert source.number == 1
        assert source.title == "Untitled"
        assert source.url == "https://example.com"
        assert source.snippet == ""
        assert source.full_content == ""
        assert source.char_count == 0

    def test_source_data_string_representation(self):
        """Test string representation of SourceData."""
        source = SourceData(
            number=5,
            title="Test Title",
            url="https://example.com",
        )
        assert str(source) == "[5] Test Title - https://example.com"

    def test_source_data_string_without_title(self):
        """Test string representation when title is None."""
        source = SourceData(
            number=3,
            title=None,
            url="https://example.com",
        )
        assert str(source) == "[3] Untitled - https://example.com"

    def test_source_data_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            SourceData()  # Missing required 'number' and 'url'

    def test_source_data_number_validation(self):
        """Test that number field accepts integers."""
        source = SourceData(number=0, url="https://example.com")
        assert source.number == 0

        source = SourceData(number=999, url="https://example.com")
        assert source.number == 999


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_search_result_creation(self):
        """Test creating a search result with valid data."""
        citations = [
            SourceData(number=1, title="Source 1", url="https://example.com/1"),
            SourceData(number=2, title="Source 2", url="https://example.com/2"),
        ]
        result = SearchResult(
            query="Test query",
            answer="Test answer",
            citations=citations,
        )
        assert result.query == "Test query"
        assert result.answer == "Test answer"
        assert len(result.citations) == 2
        assert isinstance(result.timestamp, datetime)

    def test_search_result_with_defaults(self):
        """Test creating a search result with default values."""
        result = SearchResult(query="Test query")
        assert result.query == "Test query"
        assert result.answer is None
        assert result.citations == []
        assert isinstance(result.timestamp, datetime)

    def test_search_result_string_representation(self):
        """Test string representation of SearchResult."""
        citations = [
            SourceData(number=1, url="https://example.com/1"),
            SourceData(number=2, url="https://example.com/2"),
            SourceData(number=3, url="https://example.com/3"),
        ]
        result = SearchResult(query="Test query", citations=citations)
        assert str(result) == "Search: 'Test query' (3 sources)"

    def test_search_result_timestamp_auto_generation(self):
        """Test that timestamp is automatically generated."""
        before = datetime.now()
        result = SearchResult(query="Test query")
        after = datetime.now()

        assert before <= result.timestamp <= after

    def test_search_result_empty_citations(self):
        """Test search result with no citations."""
        result = SearchResult(query="Empty query")
        assert result.citations == []
        assert str(result) == "Search: 'Empty query' (0 sources)"


class TestAgentStatesEnum:
    """Tests for AgentStatesEnum."""

    def test_agent_states_values(self):
        """Test that all agent states have correct string values."""
        assert AgentStatesEnum.INITED == "inited"
        assert AgentStatesEnum.RESEARCHING == "researching"
        assert AgentStatesEnum.WAITING_FOR_CLARIFICATION == "waiting_for_clarification"
        assert AgentStatesEnum.COMPLETED == "completed"
        assert AgentStatesEnum.ERROR == "error"
        assert AgentStatesEnum.FAILED == "failed"
        assert AgentStatesEnum.CANCELLED == "cancelled"

    def test_agent_states_finish_states(self):
        """Test that FINISH_STATES contains terminal states."""
        # FINISH_STATES is a set stored as an Enum member value
        finish_states = AgentStatesEnum.FINISH_STATES.value
        assert AgentStatesEnum.COMPLETED in finish_states
        assert AgentStatesEnum.FAILED in finish_states
        assert AgentStatesEnum.ERROR in finish_states
        assert AgentStatesEnum.CANCELLED in finish_states

    def test_agent_states_non_finish_states(self):
        """Test that non-terminal states are not in FINISH_STATES."""
        finish_states = AgentStatesEnum.FINISH_STATES.value
        assert AgentStatesEnum.INITED not in finish_states
        assert AgentStatesEnum.RESEARCHING not in finish_states
        assert AgentStatesEnum.WAITING_FOR_CLARIFICATION not in finish_states

    def test_agent_states_is_enum(self):
        """Test that AgentStatesEnum is a proper Enum."""
        from enum import Enum

        assert issubclass(AgentStatesEnum, Enum)
        assert isinstance(AgentStatesEnum.INITED, str)


class TestResearchContext:
    """Tests for ResearchContext model."""

    def test_research_context_creation(self):
        """Test creating a research context with default values."""
        context = AgentContext()
        assert context.current_step_reasoning is None
        assert context.execution_result is None
        assert context.state == AgentStatesEnum.INITED
        assert context.iteration == 0
        assert context.searches == []
        assert context.sources == {}
        assert context.searches_used == 0
        assert context.clarifications_used == 0
        assert isinstance(context.clarification_received, asyncio.Event)


class TestChatCompletionRequestAgentId:
    """Tests for ChatCompletionRequest.agent_id_from_messages computed
    field."""

    def test_agent_id_extracted_from_plain_text_messages(self):
        """Agent ID should be detected when present in plain text content."""
        from sgr_agent_core.server.models import ChatCompletionRequest

        agent_id = "sgr_agent_12345678-1234-1234-1234-123456789012"
        request = ChatCompletionRequest(
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": f"Continue agent {agent_id}"},
            ]
        )

        assert request.agent_id_from_messages == agent_id

    def test_agent_id_extracted_from_multimodal_text_part(self):
        """Agent ID should be detected when present in multimodal text part."""
        from sgr_agent_core.server.models import ChatCompletionRequest

        agent_id = "sgr_agent_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        request = ChatCompletionRequest(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Resume agent {agent_id}"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
                    ],
                }
            ]
        )

        assert request.agent_id_from_messages == agent_id

    def test_agent_id_is_none_when_absent(self):
        """agent_id_from_messages should be None when no matching pattern is
        present."""
        from sgr_agent_core.server.models import ChatCompletionRequest

        request = ChatCompletionRequest(
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Just a regular message"},
            ]
        )

        assert request.agent_id_from_messages is None

    def test_research_context_state_change(self):
        """Test changing research context state."""
        context = AgentContext()
        context.state = AgentStatesEnum.RESEARCHING
        assert context.state == AgentStatesEnum.RESEARCHING

        context.state = AgentStatesEnum.COMPLETED
        assert context.state == AgentStatesEnum.COMPLETED

    def test_research_context_iteration_increment(self):
        """Test incrementing iteration counter."""
        context = AgentContext()
        assert context.iteration == 0

        context.iteration += 1
        assert context.iteration == 1

        context.iteration += 1
        assert context.iteration == 2

    def test_research_context_add_search(self):
        """Test adding search results to context."""
        context = AgentContext()
        search = SearchResult(query="Test query")
        context.searches.append(search)

        assert len(context.searches) == 1
        assert context.searches[0].query == "Test query"

    def test_research_context_add_source(self):
        """Test adding sources to context."""
        context = AgentContext()
        source = SourceData(number=1, url="https://example.com")
        context.sources["https://example.com"] = source

        assert len(context.sources) == 1
        assert "https://example.com" in context.sources
        assert context.sources["https://example.com"].number == 1

    def test_research_context_searches_used(self):
        """Test tracking number of searches used."""
        context = AgentContext()
        assert context.searches_used == 0

        context.searches_used += 1
        assert context.searches_used == 1

        context.searches_used += 2
        assert context.searches_used == 3

    def test_research_context_clarifications_used(self):
        """Test tracking number of clarifications used."""
        context = AgentContext()
        assert context.clarifications_used == 0

        context.clarifications_used += 1
        assert context.clarifications_used == 1

    def test_research_context_agent_state_method(self):
        """Test agent_state method returns correct data."""
        context = AgentContext()
        context.state = AgentStatesEnum.RESEARCHING
        context.iteration = 5
        context.searches_used = 3
        context.clarifications_used = 1

        state = context.agent_state()

        assert isinstance(state, dict)
        assert state["state"] == AgentStatesEnum.RESEARCHING
        assert state["iteration"] == 5
        assert state["searches_used"] == 3
        assert state["clarifications_used"] == 1
        assert "searches" not in state  # Should be excluded
        assert "sources" not in state  # Should be excluded
        assert "clarification_received" not in state  # Should be excluded

    def test_research_context_agent_state_excludes_fields(self):
        """Test that agent_state excludes specific fields."""
        context = AgentContext()
        context.searches.append(SearchResult(query="Test"))
        context.sources["url"] = SourceData(number=1, url="url")

        state = context.agent_state()

        # These fields should NOT be in agent_state output
        assert "searches" not in state
        assert "sources" not in state
        assert "clarification_received" not in state

        # These fields SHOULD be in agent_state output
        assert "state" in state
        assert "iteration" in state
        assert "searches_used" in state
        assert "clarifications_used" in state

    @pytest.mark.asyncio
    async def test_research_context_clarification_event(self):
        """Test clarification event functionality."""
        context = AgentContext()

        # Event should not be set initially
        assert not context.clarification_received.is_set()

        # Set the event
        context.clarification_received.set()
        assert context.clarification_received.is_set()

        # Clear the event
        context.clarification_received.clear()
        assert not context.clarification_received.is_set()

    def test_research_context_execution_result(self):
        """Test setting execution result."""
        context = AgentContext()
        assert context.execution_result is None

        context.execution_result = "Final answer text"
        assert context.execution_result == "Final answer text"

    def test_research_context_current_step_reasoning(self):
        """Test setting current step reasoning."""
        context = AgentContext()
        assert context.current_step_reasoning is None

        reasoning_data = {"step": 1, "action": "search"}
        context.current_step_reasoning = reasoning_data
        assert context.current_step_reasoning == reasoning_data
