"""Tests for DialogAgent and dialog flow."""

from unittest.mock import MagicMock, patch

import pytest

from sgr_agent_core.agent_definition import (
    AgentDefinition,
    ExecutionConfig,
    LLMConfig,
    PromptsConfig,
)
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import DialogAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import AnswerTool
from sgr_agent_core.tools.answer_tool import PASS_TURN_TO_USER_KEY


def mock_global_config():
    """Create a mock GlobalConfig for tests."""
    mock_config = MagicMock()
    mock_config.llm = LLMConfig(api_key="default-key", base_url="https://api.openai.com/v1")
    mock_config.prompts = PromptsConfig(
        system_prompt_str="Default system prompt",
        initial_user_request_str="Default initial request",
        clarification_response_str="Default clarification response",
    )
    mock_config.execution = ExecutionConfig()
    mock_config.search = None
    mock_mcp = MagicMock()
    mock_mcp.model_copy.return_value = mock_mcp
    mock_mcp.model_dump.return_value = {}
    mock_config.mcp = mock_mcp
    return patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config)


class TestDialogAgentCreation:
    """Test DialogAgent creation and toolkit."""

    @pytest.mark.asyncio
    async def test_create_dialog_agent_from_definition(self):
        """Test creating DialogAgent from AgentDefinition."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="dialog_agent",
                base_class=DialogAgent,
                tools=["reasoningtool"],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            assert isinstance(agent, DialogAgent)
            assert agent.name == "dialog_agent"
            assert AnswerTool in agent.toolkit
            # AnswerTool should be first, then other tools from config
            assert agent.toolkit[0] is AnswerTool

    @pytest.mark.asyncio
    async def test_dialog_agent_includes_tools_from_registry(self):
        """Test DialogAgent merges AnswerTool with tools from definition."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="dialog_agent",
                base_class=DialogAgent,
                tools=["reasoningtool", "finalanswertool"],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test",
                    "initial_user_request_str": "Test",
                    "clarification_response_str": "Test",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test"}])

            assert AnswerTool in agent.toolkit
            assert len(agent.toolkit) >= 2


class TestDialogAgentAfterActionPhase:
    """Test _after_action_phase hook for AnswerTool."""

    @pytest.mark.asyncio
    async def test_after_action_phase_waits_for_answer_tool(self):
        """Test that after AnswerTool execution agent sets
        WAITING_FOR_CLARIFICATION and waits."""
        import asyncio

        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="dialog_agent",
                base_class=DialogAgent,
                tools=["reasoningtool", "answertool"],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test",
                    "initial_user_request_str": "Test",
                    "clarification_response_str": "Test",
                },
                execution=ExecutionConfig(max_iterations=5),
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Hello"}])
            agent._context.custom_context = {PASS_TURN_TO_USER_KEY: True}

            tool = AnswerTool(
                reasoning="Sharing progress",
                intermediate_result="Here is an update.",
            )

            async def release_wait():
                await asyncio.sleep(0.05)
                agent._context.clarification_received.set()

            waiter = asyncio.create_task(agent._after_action_phase(tool, "Here is an update."))
            asyncio.create_task(release_wait())
            await waiter

            assert agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION
