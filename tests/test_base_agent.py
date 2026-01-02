"""Tests for BaseAgent.

This module contains comprehensive tests for the BaseAgent class,
including initialization, logging, clarification handling, and execution
flow.
"""

import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest

from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentContext, AgentStatesEnum
from sgr_agent_core.tools import BaseTool, ReasoningTool
from tests.conftest import create_test_agent


class TestBaseAgentInitialization:
    """Tests for BaseAgent initialization and setup."""

    def test_initialization_basic(self):
        """Test basic initialization with required parameters."""
        from sgr_agent_core.agent_definition import ExecutionConfig

        agent = create_test_agent(
            BaseAgent,
            task="Test task",
            execution_config=ExecutionConfig(max_iterations=20, max_clarifications=3),
        )

        assert agent.task == "Test task"
        assert agent.name == "base_agent"
        assert agent.config.execution.max_iterations == 20
        assert agent.config.execution.max_clarifications == 3

    def test_initialization_with_custom_limits(self):
        """Test initialization with custom iteration and clarification
        limits."""
        from sgr_agent_core.agent_definition import ExecutionConfig

        agent = create_test_agent(
            BaseAgent,
            task="Test task",
            execution_config=ExecutionConfig(max_iterations=10, max_clarifications=5),
        )
        assert agent.config.execution.max_iterations == 10
        assert agent.config.execution.max_clarifications == 5

        assert agent.config.execution.max_iterations == 10
        assert agent.config.execution.max_clarifications == 5

    def test_id_generation(self):
        """Test that unique ID is generated correctly."""
        agent = create_test_agent(BaseAgent, task="Test")

        assert agent.id.startswith("base_agent_")
        # Verify UUID format
        uuid_part = agent.id.replace("base_agent_", "")
        uuid.UUID(uuid_part)  # Should not raise

    def test_multiple_agents_have_unique_ids(self):
        """Test that multiple agents get unique IDs."""
        agent1 = create_test_agent(BaseAgent, task="Task 1")
        agent2 = create_test_agent(BaseAgent, task="Task 2")

        assert agent1.id != agent2.id

    def test_toolkit_initialization_default(self):
        """Test that toolkit is initialized as empty list by default."""
        agent = create_test_agent(BaseAgent, task="Test")

        assert agent.toolkit == []

    def test_toolkit_initialization_with_custom_tools(self):
        """Test adding custom tools to toolkit."""

        class CustomTool(BaseTool):
            pass

        agent = create_test_agent(BaseAgent, task="Test", toolkit=[CustomTool])

        assert CustomTool in agent.toolkit

    def test_context_initialization(self):
        """Test that ResearchContext is initialized."""
        agent = create_test_agent(BaseAgent, task="Test")

        assert isinstance(agent._context, AgentContext)
        assert agent._context.iteration == 0
        assert agent._context.searches_used == 0
        assert agent._context.clarifications_used == 0

    def test_conversation_log_initialization(self):
        """Test that conversation and log are initialized as empty lists."""
        agent = create_test_agent(BaseAgent, task="Test")

        assert agent.conversation == []
        assert agent.log == []

    def test_creation_time_set(self):
        """Test that creation_time is set."""
        before = datetime.now()
        agent = create_test_agent(BaseAgent, task="Test")
        after = datetime.now()

        assert before <= agent.creation_time <= after

    def test_logger_initialization(self):
        """Test that logger is correctly initialized."""
        agent = create_test_agent(BaseAgent, task="Test")

        assert agent.logger is not None
        assert "sgr_agent_core.agents" in agent.logger.name
        assert agent.id in agent.logger.name


class TestBaseAgentClarificationHandling:
    """Tests for clarification handling functionality."""

    @pytest.mark.asyncio
    async def test_provide_clarification_basic(self):
        """Test basic clarification provision."""
        agent = create_test_agent(BaseAgent, task="Test")
        clarification = "This is a clarification"

        await agent.provide_clarification(clarification)

        assert len(agent.conversation) == 1
        assert agent.conversation[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_provide_clarification_increments_counter(self):
        """Test that providing clarification increments the counter."""
        agent = create_test_agent(BaseAgent, task="Test")

        await agent.provide_clarification("First clarification")
        assert agent._context.clarifications_used == 1

        await agent.provide_clarification("Second clarification")
        assert agent._context.clarifications_used == 2

    @pytest.mark.asyncio
    async def test_provide_clarification_sets_event(self):
        """Test that providing clarification sets the clarification_received
        event."""
        agent = create_test_agent(BaseAgent, task="Test")
        agent._context.clarification_received.clear()

        await agent.provide_clarification("Clarification")

        assert agent._context.clarification_received.is_set()

    @pytest.mark.asyncio
    async def test_provide_clarification_changes_state(self):
        """Test that providing clarification changes state to RESEARCHING."""
        agent = create_test_agent(BaseAgent, task="Test")
        agent._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION

        await agent.provide_clarification("Clarification")

        assert agent._context.state == AgentStatesEnum.RESEARCHING


class TestBaseAgentLogging:
    """Tests for logging functionality."""

    def test_log_reasoning_adds_to_log(self):
        """Test that _log_reasoning adds entry to log."""
        agent = create_test_agent(BaseAgent, task="Test")
        agent._context.iteration = 1

        reasoning = ReasoningTool(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Testing",
            plan_status="In progress",
            enough_data=False,
            remaining_steps=["Next step"],
            task_completed=False,
        )

        agent._log_reasoning(reasoning)

        assert len(agent.log) == 1
        assert agent.log[0]["step_type"] == "reasoning"
        assert agent.log[0]["step_number"] == 1

    def test_log_reasoning_contains_reasoning_data(self):
        """Test that logged reasoning contains all reasoning data."""
        agent = create_test_agent(BaseAgent, task="Test")

        reasoning = ReasoningTool(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Testing",
            plan_status="Good",
            enough_data=True,
            remaining_steps=["Final"],
            task_completed=False,
        )

        agent._log_reasoning(reasoning)

        log_entry = agent.log[0]
        assert "agent_reasoning" in log_entry
        assert log_entry["agent_reasoning"]["enough_data"] is True

    def test_log_tool_execution_adds_to_log(self):
        """Test that _log_tool_execution adds entry to log."""
        agent = create_test_agent(BaseAgent, task="Test")
        agent._context.iteration = 1

        tool = ReasoningTool(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Testing",
            plan_status="Good",
            enough_data=False,
            remaining_steps=["Next"],
            task_completed=False,
        )

        agent._log_tool_execution(tool, "Tool result")

        assert len(agent.log) == 1
        assert agent.log[0]["step_type"] == "tool_execution"
        assert agent.log[0]["tool_name"] == "reasoningtool"

    def test_log_tool_execution_contains_result(self):
        """Test that logged tool execution contains result."""
        agent = create_test_agent(BaseAgent, task="Test")

        tool = ReasoningTool(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Testing",
            plan_status="Good",
            enough_data=False,
            remaining_steps=["Next"],
            task_completed=False,
        )

        result = "Test execution result"
        agent._log_tool_execution(tool, result)

        log_entry = agent.log[0]
        assert log_entry["agent_tool_execution_result"] == result

    def test_log_tool_execution_with_enum_serializes_correctly(self):
        """Test that tool with enum field serializes correctly to JSON."""
        import json
        from enum import Enum

        class TestPriority(Enum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3

        class TestToolWithEnum(BaseTool):
            name: str = "test_tool"
            priority: TestPriority

        agent = create_test_agent(BaseAgent, task="Test")
        agent._context.iteration = 1

        tool = TestToolWithEnum(priority=TestPriority.HIGH)

        agent._log_tool_execution(tool, "Tool result")

        log_entry = agent.log[0]
        assert "agent_tool_context" in log_entry

        tool_context = log_entry["agent_tool_context"]
        assert isinstance(tool_context["priority"], int)
        assert tool_context["priority"] == 3

        json_str = json.dumps(log_entry, ensure_ascii=False)
        assert "3" in json_str
        assert '"priority": 3' in json_str

    def test_save_agent_log_with_enum_serializes_correctly(self, tmp_path):
        """Test that agent log with enum serializes correctly to JSON file."""
        import json
        import os
        from enum import Enum
        from unittest.mock import patch

        from sgr_agent_core.agent_definition import ExecutionConfig

        class TestStatus(Enum):
            PENDING = "pending"
            PROCESSING = "processing"
            DONE = "done"

        class TestToolWithEnum(BaseTool):
            name: str = "test_tool"
            status: TestStatus

        logs_dir = str(tmp_path / "logs")

        agent = create_test_agent(
            BaseAgent,
            task="Test",
            execution_config=ExecutionConfig(
                max_iterations=20,
                max_clarifications=3,
                logs_dir=logs_dir,
            ),
        )

        tool = TestToolWithEnum(status=TestStatus.DONE)
        agent._log_tool_execution(tool, "Result")

        mock_config = Mock()
        mock_config.execution.logs_dir = logs_dir

        with patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config):
            agent._save_agent_log()

        assert os.path.exists(logs_dir)
        log_files = list(os.listdir(logs_dir))
        assert len(log_files) == 1

        log_file_path = os.path.join(logs_dir, log_files[0])
        with open(log_file_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)

        tool_context = log_data["log"][0]["agent_tool_context"]
        assert isinstance(tool_context["status"], str)
        assert tool_context["status"] == "done"


class TestBaseAgentAbstractMethods:
    """Tests for abstract methods that must be implemented by subclasses."""

    @pytest.mark.asyncio
    async def test_prepare_tools_returns_tools(self):
        """Test that _prepare_tools returns list of tools."""
        agent = create_test_agent(BaseAgent, task="Test")

        tools = await agent._prepare_tools()
        assert isinstance(tools, list)
        # BaseAgent with empty toolkit should return empty list
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_reasoning_phase_raises_not_implemented(self):
        """Test that _reasoning_phase raises NotImplementedError."""
        agent = create_test_agent(BaseAgent, task="Test")

        with pytest.raises(NotImplementedError):
            await agent._reasoning_phase()

    @pytest.mark.asyncio
    async def test_select_action_phase_raises_not_implemented(self):
        """Test that _select_action_phase raises NotImplementedError."""
        agent = create_test_agent(BaseAgent, task="Test")
        reasoning = Mock()

        with pytest.raises(NotImplementedError):
            await agent._select_action_phase(reasoning)

    @pytest.mark.asyncio
    async def test_action_phase_raises_not_implemented(self):
        """Test that _action_phase raises NotImplementedError."""
        agent = create_test_agent(BaseAgent, task="Test")
        tool = Mock()

        with pytest.raises(NotImplementedError):
            await agent._action_phase(tool)


class TestBaseAgentPrepareContext:
    """Tests for context preparation."""

    @pytest.mark.asyncio
    async def test_prepare_context_basic(self):
        """Test basic context preparation."""
        agent = create_test_agent(BaseAgent, task="Test")
        agent.conversation = [{"role": "user", "content": "test"}]

        context = await agent._prepare_context()

        assert len(context) == 3  # system + initial_user_request + conversation
        assert context[0]["role"] == "system"
        assert context[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_prepare_context_with_multiple_messages(self):
        """Test context preparation with multiple conversation messages."""
        agent = create_test_agent(BaseAgent, task="Test")
        agent.conversation = [
            {"role": "user", "content": "message 1"},
            {"role": "assistant", "content": "response 1"},
            {"role": "user", "content": "message 2"},
        ]

        context = await agent._prepare_context()

        assert len(context) == 5  # system + initial_user_request + 3 messages

    @pytest.mark.asyncio
    async def test_prepare_context_with_image_content(self):
        """Test context preparation with image content in
        ChatCompletionMessageParam format."""
        agent = create_test_agent(BaseAgent, task="Test")
        # Simulate multimodal message with image
        agent.conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
                ],
            }
        ]

        context = await agent._prepare_context()

        # Should have: system + initial_user_request + user_context (with image) + conversation
        assert len(context) >= 3
        # Find the user message with image content
        user_messages_with_images = [
            msg for msg in context if msg.get("role") == "user" and isinstance(msg.get("content"), list)
        ]
        assert len(user_messages_with_images) > 0
        # Verify image content is preserved
        image_message = user_messages_with_images[0]
        assert isinstance(image_message["content"], list)
        assert any(part.get("type") == "image_url" for part in image_message["content"])

    @pytest.mark.asyncio
    async def test_prepare_context_no_duplicate_user_context(self):
        """Test that user_context is not duplicated when extracted from
        conversation.

        This test verifies that when user_context is extracted from conversation,
        it's not added twice (once as user_context and once as part of conversation).

        The issue: _prepare_context extracts user_context from conversation,
        then adds both user_context AND the entire conversation, causing duplication.
        """
        agent = create_test_agent(BaseAgent, task="Test")
        # Create conversation with user messages at the end
        user_msg_1 = {"role": "user", "content": "message 1"}
        user_msg_2 = {"role": "user", "content": "message 2"}
        agent.conversation = [
            {"role": "assistant", "content": "response 1"},
            user_msg_1,
            user_msg_2,
        ]

        context = await agent._prepare_context()

        # Extract user messages from context (excluding initial_user_request at index 1)
        user_messages_in_context = [msg for msg in context if msg.get("role") == "user"]
        # Skip initial_user_request (it's at index 1)
        actual_user_messages = user_messages_in_context[1:]

        # Count occurrences of each user message content
        content_counts = {}
        for msg in actual_user_messages:
            content = msg.get("content")
            content_counts[content] = content_counts.get(content, 0) + 1

        # Should have exactly 2 unique user messages, each appearing once
        # If duplication exists, we'll see message 1 and message 2 appearing twice
        expected_unique_contents = {"message 1", "message 2"}
        actual_unique_contents = set(content_counts.keys())

        # Check that we have the right messages
        assert (
            actual_unique_contents == expected_unique_contents
        ), f"Expected contents {expected_unique_contents}, got {actual_unique_contents}"

        # Check that each message appears only once (no duplication)
        for content, count in content_counts.items():
            assert count == 1, f"Message '{content}' appears {count} times, expected 1. This indicates duplication!"

    @pytest.mark.asyncio
    async def test_prepare_context_preserves_image_format(self):
        """Test that image format is preserved when preparing context for
        OpenAI client."""
        agent = create_test_agent(BaseAgent, task="Test")
        image_url = "https://example.com/test-image.jpg"
        agent.conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        context = await agent._prepare_context()

        # Find message with image
        image_messages = [
            msg
            for msg in context
            if isinstance(msg.get("content"), list)
            and any(part.get("type") == "image_url" for part in msg.get("content", []))
        ]

        assert len(image_messages) > 0, "Image message should be present in context"
        image_message = image_messages[0]
        image_parts = [part for part in image_message["content"] if part.get("type") == "image_url"]
        assert len(image_parts) > 0, "Image part should be present"
        assert image_parts[0]["image_url"]["url"] == image_url, "Image URL should be preserved"


class TestBaseAgentImageSupport:
    """Tests for image support functionality with
    ChatCompletionMessageParam."""

    @pytest.mark.asyncio
    async def test_provide_clarification_with_image(self):
        """Test providing clarification with image content."""
        agent = create_test_agent(BaseAgent, task="Test")
        clarifications = [
            {"type": "text", "text": "Here's more info"},
            {"type": "image_url", "image_url": {"url": "https://example.com/clarification.jpg"}},
        ]

        await agent.provide_clarification(clarifications)

        assert len(agent.conversation) == 1
        assert agent.conversation[0]["role"] == "user"
        content = agent.conversation[0]["content"]
        assert isinstance(content, list)
        # Should have text part wrapped in template + image part
        assert any(part.get("type") == "text" for part in content)
        assert any(part.get("type") == "image_url" for part in content)

    @pytest.mark.asyncio
    async def test_provide_clarification_image_only(self):
        """Test providing clarification with image only (no text)."""
        agent = create_test_agent(BaseAgent, task="Test")
        clarifications = [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]

        await agent.provide_clarification(clarifications)

        assert len(agent.conversation) == 1
        content = agent.conversation[0]["content"]
        assert isinstance(content, list)
        # Image-only clarification should not wrap in template
        assert any(part.get("type") == "image_url" for part in content)
        # Should not have text parts (unless template adds them)
        text_parts = [part for part in content if part.get("type") == "text"]
        # If there are text parts, they should be from template only
        if text_parts:
            assert all("clarification" in text_parts[0].get("text", "").lower() for _ in text_parts)

    @pytest.mark.asyncio
    async def test_extract_user_content_from_messages_with_images(self):
        """Test extracting user content from messages that contain images."""
        agent = create_test_agent(BaseAgent, task="Test")
        messages = [
            {"role": "assistant", "content": "Previous response"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's this?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "And this?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img2.jpg"}},
                ],
            },
        ]

        result = agent.extract_user_content_from_messages(messages)

        # Should extract last 2 consecutive user messages
        assert len(result) == 2
        assert all(msg.get("role") == "user" for msg in result)
        # Verify images are preserved
        for msg in result:
            content = msg.get("content")
            assert isinstance(content, list)
            assert any(part.get("type") == "image_url" for part in content)

    @pytest.mark.asyncio
    async def test_extract_user_content_from_messages_mixed_content(self):
        """Test extracting user content with mixed text and image messages."""
        agent = create_test_agent(BaseAgent, task="Test")
        messages = [
            {"role": "user", "content": "Text only message"},
            {"role": "assistant", "content": "Response"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Text with image"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.jpg"}},
                ],
            },
        ]

        result = agent.extract_user_content_from_messages(messages)

        # Should only extract the last user message (with image)
        assert len(result) == 1
        assert isinstance(result[0].get("content"), list)
        assert any(part.get("type") == "image_url" for part in result[0]["content"])

    @pytest.mark.asyncio
    async def test_prepare_context_includes_images_for_openai_client(self):
        """Test that _prepare_context correctly formats messages with images
        for OpenAI client.

        This test verifies that images are properly formatted as
        ChatCompletionMessageParam and will be correctly passed to
        OpenAI client's chat.completions.stream().
        """
        from unittest.mock import AsyncMock, MagicMock

        agent = create_test_agent(BaseAgent, task="Test")
        # Add multimodal message to conversation
        agent.conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Task description"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/task-image.jpg"}},
                ],
            }
        ]

        # Mock OpenAI client to capture messages
        mock_stream = AsyncMock()
        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        captured_messages = []

        async def capture_messages(*args, **kwargs):
            if "messages" in kwargs:
                captured_messages.extend(kwargs["messages"])
            return mock_stream_context

        agent.openai_client.chat.completions.stream = AsyncMock(side_effect=capture_messages)

        # Prepare context (this is what gets passed to OpenAI)
        context = await agent._prepare_context()

        # Verify context contains image message in correct format
        image_messages = [
            msg
            for msg in context
            if isinstance(msg.get("content"), list)
            and any(part.get("type") == "image_url" for part in msg.get("content", []))
        ]

        assert len(image_messages) > 0, "Context should contain messages with images"
        # Verify format is compatible with ChatCompletionMessageParam
        image_message = image_messages[0]
        assert "role" in image_message
        assert "content" in image_message
        assert isinstance(image_message["content"], list)
        # Verify image part structure
        image_part = next((part for part in image_message["content"] if part.get("type") == "image_url"), None)
        assert image_part is not None, "Image part should be present"
        assert "image_url" in image_part
        assert "url" in image_part["image_url"]


class TestBaseAgentSaveLog:
    """Tests for agent log saving functionality."""

    def test_save_agent_log_skipped_when_logs_dir_is_none(self, tmp_path):
        """Test that _save_agent_log does not create files when logs_dir is
        None."""
        from unittest.mock import patch

        from sgr_agent_core.agent_definition import ExecutionConfig

        agent = create_test_agent(
            BaseAgent,
            task="Test",
            execution_config=ExecutionConfig(
                max_iterations=20,
                max_clarifications=3,
                logs_dir=None,
            ),
        )
        agent.log = [{"step": 1, "data": "test"}]

        # Mock GlobalConfig to return None for logs_dir
        mock_config = Mock()
        mock_config.execution.logs_dir = None

        with patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config):
            # Should not raise and should not create any files
            agent._save_agent_log()

        # Verify no files were created in tmp_path
        assert list(tmp_path.iterdir()) == []

    def test_save_agent_log_skipped_when_logs_dir_is_empty_string(self, tmp_path):
        """Test that _save_agent_log does not create files when logs_dir is
        empty string."""
        from unittest.mock import patch

        from sgr_agent_core.agent_definition import ExecutionConfig

        agent = create_test_agent(
            BaseAgent,
            task="Test",
            execution_config=ExecutionConfig(
                max_iterations=20,
                max_clarifications=3,
                logs_dir="",
            ),
        )
        agent.log = [{"step": 1, "data": "test"}]

        # Mock GlobalConfig to return empty string for logs_dir
        mock_config = Mock()
        mock_config.execution.logs_dir = ""

        with patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config):
            # Should not raise and should not create any files
            agent._save_agent_log()

        # Verify no files were created
        assert list(tmp_path.iterdir()) == []

    def test_save_agent_log_creates_file_when_logs_dir_is_set(self, tmp_path):
        """Test that _save_agent_log creates log file when logs_dir is
        specified."""
        import os
        from unittest.mock import patch

        from sgr_agent_core.agent_definition import ExecutionConfig

        logs_dir = str(tmp_path / "logs")

        agent = create_test_agent(
            BaseAgent,
            task="Test",
            execution_config=ExecutionConfig(
                max_iterations=20,
                max_clarifications=3,
                logs_dir=logs_dir,
            ),
        )
        agent.log = [{"step": 1, "data": "test"}]

        # Mock GlobalConfig to return the logs_dir
        mock_config = Mock()
        mock_config.execution.logs_dir = logs_dir

        with patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config):
            agent._save_agent_log()

        # Verify log file was created
        assert os.path.exists(logs_dir)
        log_files = list(os.listdir(logs_dir))
        assert len(log_files) == 1
        assert log_files[0].endswith("-log.json")
