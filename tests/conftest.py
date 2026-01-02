"""Pytest configuration and fixtures for tests."""

from typing import Type
from unittest.mock import Mock

import pytest
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from sgr_agent_core import ExecutionConfig, LLMConfig, PromptsConfig
from sgr_agent_core.agent_definition import AgentConfig
from sgr_agent_core.base_agent import BaseAgent


def create_test_agent(
    agent_class: Type[BaseAgent],
    task_messages: list[ChatCompletionMessageParam] | None = None,
    openai_client: AsyncOpenAI | None = None,
    llm_config: LLMConfig | None = None,
    prompts_config: PromptsConfig | None = None,
    execution_config: ExecutionConfig | None = None,
    toolkit: list | None = None,
) -> BaseAgent:
    """Create an agent instance for testing.

    Args:
        agent_class: Agent class to instantiate
        task_messages: Task messages for the agent (defaults to single user message)
        openai_client: OpenAI client (will be mocked if None)
        llm_config: LLM configuration (will use defaults if None)
        prompts_config: Prompts configuration (will use defaults if None)
        execution_config: Execution configuration (will use defaults if None)
        toolkit: List of tools (will be empty if None)

    Returns:
        Created agent instance
    """
    if task_messages is None:
        task_messages = [{"role": "user", "content": "Test task"}]

    if openai_client is None:
        openai_client = Mock(spec=AsyncOpenAI)

    if llm_config is None:
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )

    if prompts_config is None:
        prompts_config = PromptsConfig(
            system_prompt_str="Test system prompt",
            initial_user_request_str="Test initial request",
            clarification_response_str="Test clarification response",
        )

    if execution_config is None:
        execution_config = ExecutionConfig(
            max_iterations=20,
            max_clarifications=3,
            max_searches=4,
        )

    agent_config = AgentConfig(
        llm=llm_config,
        prompts=prompts_config,
        execution=execution_config,
    )

    return agent_class(
        task_messages=task_messages,
        openai_client=openai_client,
        agent_config=agent_config,
        toolkit=toolkit or [],
    )


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    return Mock(spec=AsyncOpenAI)


@pytest.fixture
def test_llm_config():
    """Create a test LLM configuration."""
    return LLMConfig(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )


@pytest.fixture
def test_prompts_config():
    """Create a test prompts configuration."""
    return PromptsConfig(
        system_prompt_str="Test system prompt",
        initial_user_request_str="Test initial request",
        clarification_response_str="Test clarification response",
    )


@pytest.fixture
def test_execution_config():
    """Create a test execution configuration."""
    return ExecutionConfig(
        max_iterations=20,
        max_clarifications=3,
        max_searches=4,
    )
