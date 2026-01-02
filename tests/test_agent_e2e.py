"""End-to-end tests for agent execution workflow."""

from typing import Type
from unittest.mock import Mock

import pytest
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionMessageToolCall
from openai.types.chat.chat_completion import Choice

from sgr_agent_core.agent_definition import AgentConfig, ExecutionConfig, LLMConfig, PromptsConfig
from sgr_agent_core.agents import SGRAgent, SGRToolCallingAgent, ToolCallingAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.next_step_tool import NextStepToolsBuilder
from sgr_agent_core.tools import AdaptPlanTool, FinalAnswerTool, ReasoningTool


class MockStream:
    """Mock OpenAI stream object."""

    def __init__(self, final_completion_data: dict):
        self._final_completion_data = final_completion_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def get_final_completion(self) -> ChatCompletion:
        message = ChatCompletionMessage(
            role="assistant",
            content=self._final_completion_data.get("content"),
            tool_calls=self._final_completion_data.get("tool_calls"),
        )
        if "parsed" in self._final_completion_data:
            setattr(message, "parsed", self._final_completion_data["parsed"])

        return ChatCompletion(
            id="test-completion-id",
            choices=[Choice(index=0, message=message, finish_reason="stop")],
            created=1234567890,
            model="gpt-4o-mini",
            object="chat.completion",
        )


def _create_tool_call(tool: Type, call_id: str) -> ChatCompletionMessageToolCall:
    tool_call = Mock(spec=ChatCompletionMessageToolCall)
    tool_call.id = call_id
    tool_call.type = "function"
    tool_call.function = Mock()
    tool_call.function.name = tool.tool_name
    tool_call.function.parsed_arguments = tool
    return tool_call


def _create_next_step_tool_response(tool_class: Type, tool_data: dict, reasoning_data: dict) -> Type:
    NextStepTools = NextStepToolsBuilder.build_NextStepTools([tool_class])
    tool_dict = tool_data.copy()
    tool_dict["tool_name_discriminator"] = tool_class.tool_name
    return NextStepTools(function=tool_dict, **reasoning_data)


def create_mock_openai_client_for_sgr_agent(action_tool_1: Type, action_tool_2: Type) -> AsyncOpenAI:
    client = Mock(spec=AsyncOpenAI)

    response_1 = _create_next_step_tool_response(
        action_tool_1,
        {
            "reasoning": "Plan needs to be adapted based on initial findings",
            "original_goal": "Research task",
            "new_goal": "Updated research goal",
            "plan_changes": ["Change 1", "Change 2"],
            "next_steps": ["Step 1", "Step 2", "Step 3"],
        },
        {
            "reasoning_steps": ["Step 1: Analyze task", "Step 2: Plan adaptation"],
            "current_situation": "Initial research phase",
            "plan_status": "Plan needs adaptation",
            "enough_data": False,
            "remaining_steps": ["Adapt plan", "Continue research"],
            "task_completed": False,
        },
    )

    response_2 = _create_next_step_tool_response(
        action_tool_2,
        {
            "reasoning": "Task completed successfully",
            "completed_steps": ["Step 1", "Step 2"],
            "answer": "Final answer to the research task",
            "status": AgentStatesEnum.COMPLETED,
        },
        {
            "reasoning_steps": ["Step 1: Complete research", "Step 2: Finalize answer"],
            "current_situation": "Research completed",
            "plan_status": "All steps completed",
            "enough_data": True,
            "remaining_steps": ["Finalize"],
            "task_completed": True,
        },
    )

    call_count = {"count": 0}

    def mock_stream(**kwargs):
        call_count["count"] += 1
        response = response_1 if call_count["count"] == 1 else response_2
        return MockStream(final_completion_data={"parsed": response})

    client.chat.completions.stream = Mock(side_effect=mock_stream)
    return client


def create_mock_openai_client_for_tool_calling_agent(action_tool_1: Type, action_tool_2: Type) -> AsyncOpenAI:
    client = Mock(spec=AsyncOpenAI)

    tool_1 = action_tool_1(
        reasoning="Plan needs to be adapted",
        original_goal="Research task",
        new_goal="Updated research goal",
        plan_changes=["Change 1", "Change 2"],
        next_steps=["Step 1", "Step 2", "Step 3"],
    )

    tool_2 = action_tool_2(
        reasoning="Task completed successfully",
        completed_steps=["Step 1", "Step 2"],
        answer="Final answer to the research task",
        status=AgentStatesEnum.COMPLETED,
    )

    call_count = {"count": 0}

    def mock_stream(**kwargs):
        call_count["count"] += 1
        tool = tool_1 if call_count["count"] == 1 else tool_2
        return MockStream(
            final_completion_data={
                "content": None,
                "role": "assistant",
                "tool_calls": [_create_tool_call(tool, f"call_{call_count['count']}")],
            }
        )

    client.chat.completions.stream = Mock(side_effect=mock_stream)
    return client


def create_mock_openai_client_for_sgr_tool_calling_agent(action_tool_1: Type, action_tool_2: Type) -> AsyncOpenAI:
    client = Mock(spec=AsyncOpenAI)

    reasoning_tools = [
        ReasoningTool(
            reasoning_steps=["Step 1: Analyze", "Step 2: Plan"],
            current_situation="Initial research phase",
            plan_status="Plan needs adaptation",
            enough_data=False,
            remaining_steps=["Adapt plan", "Continue"],
            task_completed=False,
        ),
        ReasoningTool(
            reasoning_steps=["Step 1: Complete", "Step 2: Finalize"],
            current_situation="Research completed",
            plan_status="All steps completed",
            enough_data=True,
            remaining_steps=["Finalize"],
            task_completed=True,
        ),
    ]

    action_tools = [
        action_tool_1(
            reasoning="Plan needs to be adapted",
            original_goal="Research task",
            new_goal="Updated research goal",
            plan_changes=["Change 1", "Change 2"],
            next_steps=["Step 1", "Step 2", "Step 3"],
        ),
        action_tool_2(
            reasoning="Task completed successfully",
            completed_steps=["Step 1", "Step 2"],
            answer="Final answer to the research task",
            status=AgentStatesEnum.COMPLETED,
        ),
    ]

    reasoning_count = {"count": 0}
    action_count = {"count": 0}

    def mock_stream(**kwargs):
        is_reasoning = (
            "tool_choice" in kwargs
            and isinstance(kwargs.get("tool_choice"), dict)
            and kwargs["tool_choice"].get("function", {}).get("name") == ReasoningTool.tool_name
        )

        if is_reasoning:
            reasoning_count["count"] += 1
            tool = reasoning_tools[reasoning_count["count"] - 1]
            call_id = f"reasoning_{reasoning_count['count']}"
        else:
            tools_param = kwargs.get("tools")
            if tools_param is not None and not isinstance(tools_param, list):
                raise TypeError(
                    f"SGRToolCallingAgent._prepare_tools() must return a list, "
                    f"but got {type(tools_param).__name__}. "
                    f"Override _prepare_tools() to return list instead of NextStepToolStub."
                )
            action_count["count"] += 1
            tool = action_tools[action_count["count"] - 1]
            call_id = f"action_{action_count['count']}"

        return MockStream(
            final_completion_data={
                "content": None,
                "role": "assistant",
                "tool_calls": [_create_tool_call(tool, call_id)],
            }
        )

    client.chat.completions.stream = Mock(side_effect=mock_stream)
    return client


def _create_test_agent_config() -> AgentConfig:
    return AgentConfig(
        llm=LLMConfig(api_key="test-key", base_url="https://api.openai.com/v1", model="gpt-4o-mini"),
        prompts=PromptsConfig(
            system_prompt_str="Test system prompt",
            initial_user_request_str="Test initial request",
            clarification_response_str="Test clarification response",
        ),
        execution=ExecutionConfig(max_iterations=10, max_clarifications=3, max_searches=5),
    )


def _assert_agent_completed(agent, expected_result: str = "Final answer to the research task"):
    assert agent._context.state == AgentStatesEnum.COMPLETED
    assert agent._context.execution_result == expected_result
    assert agent._context.iteration >= 2
    assert len(agent.conversation) > 0
    assert len(agent.log) > 0


@pytest.mark.asyncio
async def test_sgr_agent_full_execution_cycle():
    agent = SGRAgent(
        task_messages=[{"role": "user", "content": "Test research task"}],
        openai_client=create_mock_openai_client_for_sgr_agent(AdaptPlanTool, FinalAnswerTool),
        agent_config=_create_test_agent_config(),
        toolkit=[FinalAnswerTool, AdaptPlanTool],
    )

    assert agent._context.state == AgentStatesEnum.INITED
    assert agent._context.iteration == 0

    result = await agent.execute()

    assert result is not None
    _assert_agent_completed(agent)


@pytest.mark.asyncio
async def test_tool_calling_agent_full_execution_cycle():
    agent = ToolCallingAgent(
        task_messages=[{"role": "user", "content": "Test research task"}],
        openai_client=create_mock_openai_client_for_tool_calling_agent(AdaptPlanTool, FinalAnswerTool),
        agent_config=_create_test_agent_config(),
        toolkit=[FinalAnswerTool, AdaptPlanTool],
    )

    assert agent._context.state == AgentStatesEnum.INITED
    assert agent._context.iteration == 0

    result = await agent.execute()

    assert result is not None
    _assert_agent_completed(agent)


@pytest.mark.asyncio
async def test_sgr_tool_calling_agent_full_execution_cycle():
    """Validates that SGRToolCallingAgent overrides _prepare_tools()
    correctly."""
    agent = SGRToolCallingAgent(
        task_messages=[{"role": "user", "content": "Test research task"}],
        openai_client=create_mock_openai_client_for_sgr_tool_calling_agent(AdaptPlanTool, FinalAnswerTool),
        agent_config=_create_test_agent_config(),
        toolkit=[FinalAnswerTool, AdaptPlanTool],
    )

    assert agent._context.state == AgentStatesEnum.INITED
    assert agent._context.iteration == 0

    result = await agent.execute()

    assert result is not None
    _assert_agent_completed(agent)
