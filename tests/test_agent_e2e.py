"""End-to-end tests for agent execution workflow.

Run explicitly: pytest -m e2e
"""

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

pytestmark = pytest.mark.e2e


class MockStream:
    """Mock OpenAI stream object that emulates OpenAI streaming API.

    This mock properly handles:
    - Context manager protocol (async with)
    - Stream iteration (async for event in stream)
    - Final completion retrieval with parsed_arguments support
    """

    def __init__(self, final_completion_data: dict):
        """Initialize mock stream with final completion data.

        Args:
            final_completion_data: Dictionary containing:
                - content: Optional message content
                - tool_calls: List of tool call objects (already with parsed_arguments set)
        """
        self._final_completion_data = final_completion_data
        self._iterated = False

    async def __aenter__(self):
        """Enter context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        pass

    def __aiter__(self):
        """Return iterator for stream events."""
        return self

    async def __anext__(self):
        """Return next stream event (empty iterator for simplicity).

        In real OpenAI API, this would yield chunk events. For testing,
        we return empty iterator since the code handles missing chunks
        gracefully.
        """
        if self._iterated:
            raise StopAsyncIteration
        self._iterated = True
        raise StopAsyncIteration

    async def get_final_completion(self) -> ChatCompletion:
        """Get final completion with parsed tool call arguments or structured
        output.

        Supports both formats:
        - Structured output: message.parsed (for SGRAgent)
        - Function calling: tool_calls[0].function.parsed_arguments (for SGRToolCallingAgent)

        Returns:
            ChatCompletion object with appropriate parsed data
        """
        tool_calls = self._final_completion_data.get("tool_calls", [])

        message = ChatCompletionMessage(
            role="assistant",
            content=self._final_completion_data.get("content"),
            tool_calls=tool_calls if tool_calls else None,
        )

        # Support structured output format (SGRAgent uses message.parsed)
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
    """Create a mock OpenAI client for SGRToolCallingAgent tests.

    Args:
        action_tool_1: First action tool to return (e.g., AdaptPlanTool)
        action_tool_2: Second action tool to return (e.g., FinalAnswerTool)

    Returns:
        Mocked AsyncOpenAI client configured for SGRToolCallingAgent execution cycle
    """
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
        """Mock stream function that returns appropriate tool based on tool
        name."""
        tools_param = kwargs.get("tools", [])

        # Validate that tools is a list
        if not isinstance(tools_param, list):
            raise TypeError(
                f"SGRToolCallingAgent._prepare_tools() must return a list, "
                f"but got {type(tools_param).__name__}. "
                f"Override _prepare_tools() to return list instead of NextStepToolStub."
            )

        # Get tool name from first tool in the list
        tool_name = None
        if tools_param:
            first_tool = tools_param[0]
            if isinstance(first_tool, dict):
                tool_name = first_tool.get("function", {}).get("name")

        # Return appropriate tool based on name
        if tool_name == ReasoningTool.tool_name:
            reasoning_count["count"] += 1
            tool = reasoning_tools[reasoning_count["count"] - 1]
        else:
            # Action tool - use counter to select from action_tools list
            action_count["count"] += 1
            tool = action_tools[action_count["count"] - 1]

        # call_id is not used by agent, just needed for valid OpenAI API structure
        return MockStream(
            final_completion_data={
                "content": None,
                "tool_calls": [_create_tool_call(tool, "mock-call-id")],
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


@pytest.mark.asyncio
async def test_sgr_tool_calling_agent_custom_reasoning_tool_is_used():
    """Custom ReasoningTool is actually passed to OpenAI in _reasoning_phase.

    Verifies that self.ReasoningTool is forwarded to
    pydantic_function_tool() instead of the hardcoded base
    ReasoningTool.
    """
    from pydantic import Field as PydanticField

    class CustomReasoningTool(ReasoningTool):
        confidence: float = PydanticField(default=0.5, description="Confidence in the decision")

    captured_reasoning_tool_names: list[str] = []

    reasoning_instance = CustomReasoningTool(
        reasoning_steps=["Analyze", "Decide"],
        current_situation="Test situation",
        plan_status="On track",
        enough_data=False,
        remaining_steps=["Finalize"],
        task_completed=False,
        confidence=0.9,
    )
    final_answer_instance = FinalAnswerTool(
        reasoning="Done",
        completed_steps=["Step 1"],
        answer="Final answer to the research task",
        status=AgentStatesEnum.COMPLETED,
    )

    client = Mock(spec=AsyncOpenAI)

    def mock_stream(**kwargs):
        tools_param = kwargs.get("tools", [])
        tool_name = None
        if tools_param and isinstance(tools_param, list) and isinstance(tools_param[0], dict):
            tool_name = tools_param[0].get("function", {}).get("name")

        if tool_name == CustomReasoningTool.tool_name:
            captured_reasoning_tool_names.append(tool_name)
            return MockStream({"content": None, "tool_calls": [_create_tool_call(reasoning_instance, "call-r")]})

        return MockStream({"content": None, "tool_calls": [_create_tool_call(final_answer_instance, "call-a")]})

    client.chat.completions.stream = Mock(side_effect=mock_stream)

    agent = SGRToolCallingAgent(
        task_messages=[{"role": "user", "content": "Test task"}],
        openai_client=client,
        agent_config=_create_test_agent_config(),
        toolkit=[FinalAnswerTool],
        reasoning_tool_cls=CustomReasoningTool,
    )

    result = await agent.execute()

    assert result is not None
    assert agent._context.state == AgentStatesEnum.COMPLETED
    assert len(captured_reasoning_tool_names) >= 1, "Custom ReasoningTool was never passed to OpenAI"
    assert captured_reasoning_tool_names[0] == CustomReasoningTool.tool_name


@pytest.mark.asyncio
async def test_sgr_agent_custom_reasoning_tool_is_used():
    """Custom ReasoningTool is used as SO base in SGRAgent._reasoning_phase.

    Verifies that response_format passed to OpenAI is built on top of
    the custom ReasoningTool subclass rather than the default one.
    """
    from pydantic import Field as PydanticField

    class CustomReasoningTool(ReasoningTool):
        confidence: float = PydanticField(default=0.5, description="Confidence in the decision")

    captured_response_formats: list[type] = []

    client = Mock(spec=AsyncOpenAI)

    def mock_stream(**kwargs):
        response_format = kwargs.get("response_format")
        if response_format is not None:
            captured_response_formats.append(response_format)

        NextStepTools = NextStepToolsBuilder.build_NextStepTools(
            [FinalAnswerTool],
            base_reasoning_cls=CustomReasoningTool,
        )
        response = NextStepTools(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Test",
            plan_status="Ok",
            enough_data=True,
            remaining_steps=["Finalize"],
            task_completed=True,
            confidence=0.8,
            function={
                "tool_name_discriminator": FinalAnswerTool.tool_name,
                "reasoning": "Done",
                "completed_steps": ["Step 1"],
                "answer": "Final answer to the research task",
                "status": AgentStatesEnum.COMPLETED,
            },
        )
        return MockStream({"parsed": response})

    client.chat.completions.stream = Mock(side_effect=mock_stream)

    agent = SGRAgent(
        task_messages=[{"role": "user", "content": "Test task"}],
        openai_client=client,
        agent_config=_create_test_agent_config(),
        toolkit=[FinalAnswerTool],
        reasoning_tool_cls=CustomReasoningTool,
    )

    result = await agent.execute()

    assert result is not None
    assert agent._context.state == AgentStatesEnum.COMPLETED
    assert len(captured_response_formats) >= 1, "response_format was never passed to OpenAI"
    assert issubclass(
        captured_response_formats[0], CustomReasoningTool
    ), f"response_format {captured_response_formats[0]} is not a subclass of CustomReasoningTool"
