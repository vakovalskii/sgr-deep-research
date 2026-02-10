"""Tests for streaming functionality.

This module contains comprehensive tests for the BaseStreamingGenerator,
OpenAIStreamingGenerator, OpenWebUIStreamingGenerator, and
StreamingGeneratorRegistry.
"""

import json

import pytest

from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.services.registry import StreamingGeneratorRegistry
from sgr_agent_core.stream import (
    BaseStreamingGenerator,
    OpenAIStreamingGenerator,
    OpenWebUIStreamingGenerator,
)
from sgr_agent_core.tools.final_answer_tool import FinalAnswerTool


class TestBaseStreamingGenerator:
    """Tests for base BaseStreamingGenerator class."""

    def test_initialization(self):
        """Test that BaseStreamingGenerator initializes correctly."""
        generator = BaseStreamingGenerator()
        assert generator.queue is not None
        assert generator.queue.qsize() == 0

    def test_add_single_item(self):
        """Test adding a single item to the queue."""
        generator = BaseStreamingGenerator()
        generator.add("test data")
        assert generator.queue.qsize() == 1

    def test_add_multiple_items(self):
        """Test adding multiple items to the queue."""
        generator = BaseStreamingGenerator()
        generator.add("item 1")
        generator.add("item 2")
        generator.add("item 3")
        assert generator.queue.qsize() == 3

    def test_finish_adds_none(self):
        """Test that finish() adds None as termination signal."""
        generator = BaseStreamingGenerator()
        generator.add("data")
        generator.finish()

        # Queue should have 2 items: "data" and None
        assert generator.queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_stream_empty(self):
        """Test streaming with no data (only finish)."""
        generator = BaseStreamingGenerator()
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_stream_single_item(self):
        """Test streaming a single item."""
        generator = BaseStreamingGenerator()
        generator.add("test data")
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert len(items) == 1
        assert items[0] == "test data"

    @pytest.mark.asyncio
    async def test_stream_multiple_items(self):
        """Test streaming multiple items."""
        generator = BaseStreamingGenerator()
        test_items = ["item 1", "item 2", "item 3"]
        for item in test_items:
            generator.add(item)
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert items == test_items

    @pytest.mark.asyncio
    async def test_stream_order_preserved(self):
        """Test that streaming preserves item order."""
        generator = BaseStreamingGenerator()
        expected_order = ["first", "second", "third", "fourth"]
        for item in expected_order:
            generator.add(item)
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert items == expected_order

    @pytest.mark.asyncio
    async def test_stream_terminates_on_none(self):
        """Test that stream terminates when None is encountered."""
        generator = BaseStreamingGenerator()
        generator.add("data 1")
        generator.add("data 2")
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        # Should not include None in results
        assert None not in items
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_stream_with_unicode(self):
        """Test streaming with Unicode characters."""
        generator = BaseStreamingGenerator()
        unicode_data = ["Hello 世界", "Привет мир", "こんにちは 🌍"]
        for item in unicode_data:
            generator.add(item)
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert items == unicode_data

    @pytest.mark.asyncio
    async def test_stream_with_long_strings(self):
        """Test streaming with very long strings."""
        generator = BaseStreamingGenerator()
        long_string = "A" * 10000
        generator.add(long_string)
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert len(items) == 1
        assert items[0] == long_string

    @pytest.mark.asyncio
    async def test_stream_with_special_characters(self):
        """Test streaming with special characters."""
        generator = BaseStreamingGenerator()
        special_chars = ["<>&\"'", "$%^&*()", "{}[]\\|"]
        for item in special_chars:
            generator.add(item)
        generator.finish()

        items = []
        async for item in generator.stream():
            items.append(item)

        assert items == special_chars


TEST_PHASE_ID = "test-phase"


class TestOpenAIStreamingGenerator:
    """Tests for OpenAIStreamingGenerator class."""

    def test_initialization_with_agent_id(self):
        """Test initialization with agent_id."""
        generator = OpenAIStreamingGenerator(agent_id="test-agent-1")
        assert generator.agent_id == "test-agent-1"

    def test_initialization_custom_agent_id(self):
        """Test initialization with custom agent_id."""
        generator = OpenAIStreamingGenerator(agent_id="custom-agent-id")
        assert generator.agent_id == "custom-agent-id"

    def test_choice_index_default(self):
        """Test that choice_index defaults to 0."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        assert generator.choice_index == 0

    def test_inherits_from_streaming_generator(self):
        """Test that OpenAIStreamingGenerator inherits from
        BaseStreamingGenerator."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        assert isinstance(generator, BaseStreamingGenerator)

    @pytest.mark.asyncio
    async def test_add_content_delta_format(self):
        """Test that add_content_delta creates correct format."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.add_content_delta("Hello", TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        assert len(items) >= 2
        assert items[0].startswith("data: ")

    @pytest.mark.asyncio
    async def test_add_content_delta_json_structure(self):
        """Test that add_content_delta produces valid JSON."""
        generator = OpenAIStreamingGenerator(agent_id="test-agent-id")
        generator.add_content_delta("Test content", TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        assert first_chunk.startswith("data: ")
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["object"] == "chat.completion.chunk"
        assert data["model"] == "test-agent-id"
        assert data["choices"][0]["delta"]["content"] == "Test content"
        assert data["choices"][0]["delta"]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_add_content_delta_content(self):
        """Test that content is correctly set in chunk."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        test_content = "This is test content"
        generator.add_content_delta(test_content, TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["delta"]["content"] == test_content

    @pytest.mark.asyncio
    async def test_add_content_delta_multiple(self):
        """Test adding multiple content chunks."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        contents = ["Hello", " world", "!"]
        for content in contents:
            generator.add_content_delta(content, TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        assert len(items) >= 4

    @pytest.mark.asyncio
    async def test_finish_creates_final_chunk(self):
        """Test that finish() creates proper final chunk."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.add_content_delta("content", TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        final_chunk = items[-2]
        json_str = final_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["finish_reason"] == "stop"
        assert "usage" in data

    @pytest.mark.asyncio
    async def test_finish_with_custom_reason(self):
        """Test finish() with custom finish_reason."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.finish(TEST_PHASE_ID, finish_reason="length")

        items = []
        async for item in generator.stream():
            items.append(item)

        final_chunk = items[-2]
        json_str = final_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["finish_reason"] == "length"

    @pytest.mark.asyncio
    async def test_finish_includes_usage(self):
        """Test that final chunk includes usage information."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        final_chunk = items[-2]
        json_str = final_chunk[6:].strip()
        data = json.loads(json_str)

        assert "usage" in data
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert "total_tokens" in data["usage"]

    @pytest.mark.asyncio
    async def test_add_tool_result_format(self):
        """Test that add_tool_result produces chunk with role tool and
        content."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.add_tool_result(TEST_PHASE_ID, '{"result": "ok"}', tool_name="my_tool")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        assert first_chunk.startswith("data: ")
        data = json.loads(first_chunk[6:].strip())
        assert data["object"] == "chat.completion.chunk"
        delta = data["choices"][0]["delta"]
        assert delta["role"] == "tool"
        assert delta["content"] == '{"result": "ok"}'
        assert delta["tool_call_id"] == TEST_PHASE_ID

    @pytest.mark.asyncio
    async def test_finish_adds_done_marker(self):
        """Test that finish() adds [DONE] marker."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        assert items[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_complete_flow_text_only(self):
        """Test complete flow with text content only."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.add_content_delta("Hello", TEST_PHASE_ID)
        generator.add_content_delta(" world", TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        assert len(items) == 4

    @pytest.mark.asyncio
    async def test_unicode_in_content(self):
        """Test Unicode characters in content."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        unicode_content = "Hello 世界 🌍 Привет"
        generator.add_content_delta(unicode_content, TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["delta"]["content"] == unicode_content

    @pytest.mark.asyncio
    async def test_special_characters_in_content(self):
        """Test special characters in content."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        special_content = 'Test with "quotes" and <tags> and $pecial chars'
        generator.add_content_delta(special_content, TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["delta"]["content"] == special_content

    @pytest.mark.asyncio
    async def test_newlines_in_content(self):
        """Test newlines in content."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        multiline_content = "Line 1\nLine 2\nLine 3"
        generator.add_content_delta(multiline_content, TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["delta"]["content"] == multiline_content

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """Test adding empty content."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.add_content_delta("", TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert data["choices"][0]["delta"]["content"] == ""

    @pytest.mark.asyncio
    async def test_sse_format_compliance(self):
        """Test that output follows SSE format (data: prefix, double
        newline)."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        generator.add_content_delta("test", TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        for item in items:
            assert item.startswith("data: ")
            assert item.endswith("\n\n")

    def test_agent_id_preserved_across_chunks(self):
        """Test that agent_id is consistent across generator."""
        generator = OpenAIStreamingGenerator(agent_id="custom-agent-id")
        assert generator.agent_id == "custom-agent-id"

    def test_agent_id_consistent_across_session(self):
        """Test that agent_id remains consistent within a generator
        instance."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        first_id = generator.agent_id
        generator.add_content_delta("test", TEST_PHASE_ID)
        second_id = generator.agent_id

        assert first_id == second_id

    @pytest.mark.asyncio
    async def test_multiple_generators_independent(self):
        """Test that multiple generators are independent."""
        import asyncio

        gen1 = OpenAIStreamingGenerator(agent_id="agent-1")
        await asyncio.sleep(0.001)
        gen2 = OpenAIStreamingGenerator(agent_id="agent-2")

        gen1.add_content_delta("content1", TEST_PHASE_ID)
        gen2.add_content_delta("content2", TEST_PHASE_ID)

        assert gen1.agent_id != gen2.agent_id
        assert gen1.queue != gen2.queue

    @pytest.mark.asyncio
    async def test_long_content_stream(self):
        """Test streaming very long content."""
        generator = OpenAIStreamingGenerator(agent_id="test-id")
        long_content = "A" * 10000
        generator.add_content_delta(long_content, TEST_PHASE_ID)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        first_chunk = items[0]
        json_str = first_chunk[6:].strip()
        data = json.loads(json_str)

        assert len(data["choices"][0]["delta"]["content"]) == 10000


class TestOpenWebUIStreamingGenerator:
    """Tests for OpenWebUIStreamingGenerator (details/markdown protocol)."""

    def test_initialization(self):
        """Test initialization with agent_id."""
        generator = OpenWebUIStreamingGenerator(agent_id="webui-agent")
        assert generator.agent_id == "webui-agent"
        assert isinstance(generator, OpenAIStreamingGenerator)

    @pytest.mark.asyncio
    async def test_add_chunk_is_noop(self):
        """Test that add_chunk does not add to queue (no raw chunks in
        open_webui)."""
        from openai.types.chat import ChatCompletionChunk

        generator = OpenWebUIStreamingGenerator(agent_id="test-id")
        chunk = ChatCompletionChunk(
            id="c",
            object="chat.completion.chunk",
            created=0,
            model="m",
            choices=[{"index": 0, "delta": {"content": "x"}, "finish_reason": None}],
        )
        generator.add_chunk(chunk, "phase-1")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        # Only finish chunk and [DONE]; no content from add_chunk
        data_lines = [i for i in items if i.startswith("data: ") and "[DONE]" not in i]
        assert len(data_lines) == 1
        data = json.loads(data_lines[0][6:].strip())
        assert data["choices"][0].get("finish_reason") == "stop"

    @pytest.mark.asyncio
    async def test_add_tool_call_produces_details_markdown(self):
        """Test that add_tool_call sends <details> with phase, tool name and
        JSON block."""
        tool = FinalAnswerTool(
            reasoning="done",
            completed_steps=["step1"],
            answer="Final answer",
            status=AgentStatesEnum.COMPLETED,
        )
        generator = OpenWebUIStreamingGenerator(agent_id="test-id")
        generator.add_tool_call(TEST_PHASE_ID, tool)
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        content_chunk = items[0]
        data = json.loads(content_chunk[6:].strip())
        content = data["choices"][0]["delta"]["content"]
        assert "<details>" in content
        assert "<summary>" in content
        assert f"Phase: {TEST_PHASE_ID}" in content
        assert "Tool Call: finalanswertool" in content or "final_answer" in content
        assert "```" in content
        assert "reasoning" in content or "answer" in content

    @pytest.mark.asyncio
    async def test_add_tool_result_json_wraps_in_code_block(self):
        """Test that add_tool_result with JSON wraps in json code block."""
        generator = OpenWebUIStreamingGenerator(agent_id="test-id")
        generator.add_tool_result(TEST_PHASE_ID, '{"key": "value"}', tool_name="search")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        content_chunk = items[0]
        data = json.loads(content_chunk[6:].strip())
        content = data["choices"][0]["delta"]["content"]
        assert "<details>" in content
        assert "Tool Result: search" in content
        assert "``` json" in content or "```json" in content
        assert '{"key": "value"}' in content

    @pytest.mark.asyncio
    async def test_add_tool_result_plain_wraps_in_code_block(self):
        """Test that add_tool_result with non-JSON uses plain code block."""
        generator = OpenWebUIStreamingGenerator(agent_id="test-id")
        generator.add_tool_result(TEST_PHASE_ID, "plain text result", tool_name="custom")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        content_chunk = items[0]
        data = json.loads(content_chunk[6:].strip())
        content = data["choices"][0]["delta"]["content"]
        assert "<details>" in content
        assert "Tool Result: custom" in content
        assert "plain text result" in content

    @pytest.mark.asyncio
    async def test_finish_inherited_works(self):
        """Test that finish() still produces [DONE] and final chunk."""
        generator = OpenWebUIStreamingGenerator(agent_id="test-id")
        generator.finish(TEST_PHASE_ID)

        items = []
        async for item in generator.stream():
            items.append(item)

        assert items[-1] == "data: [DONE]\n\n"
        data = json.loads(items[-2][6:].strip())
        assert data["choices"][0]["finish_reason"] == "stop"


class TestStreamingGeneratorRegistry:
    """Tests for StreamingGeneratorRegistry resolution by name."""

    def test_get_openai_returns_openai_generator_class(self):
        """Test that Registry.get('openai') returns
        OpenAIStreamingGenerator."""
        cls = StreamingGeneratorRegistry.get("openai")
        assert cls is OpenAIStreamingGenerator

    def test_get_open_webui_returns_open_webui_generator_class(self):
        """Test that Registry.get('open_webui') returns
        OpenWebUIStreamingGenerator."""
        cls = StreamingGeneratorRegistry.get("open_webui")
        assert cls is OpenWebUIStreamingGenerator

    def test_get_unknown_returns_none(self):
        """Test that unknown name returns None."""
        assert StreamingGeneratorRegistry.get("unknown_generator") is None

    def test_get_case_insensitive(self):
        """Test that get is case-insensitive."""
        assert StreamingGeneratorRegistry.get("OpenAI") is OpenAIStreamingGenerator
        assert StreamingGeneratorRegistry.get("OPEN_WEBUI") is OpenWebUIStreamingGenerator

    def test_list_items_includes_builtin_generators(self):
        """Test that list_items includes at least openai and open_webui."""
        items = StreamingGeneratorRegistry.list_items()
        names = {c.name for c in items}
        assert "openai" in names
        assert "open_webui" in names
