"""End-to-end test: autonomous skill invocation through the agent loop.

Run explicitly: pytest -m e2e
"""

from typing import Type
from unittest.mock import Mock

import pytest
from openai import AsyncOpenAI

from sgr_agent_core.agents import SGRAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.next_step_tool import NextStepToolsBuilder
from sgr_agent_core.skills import Skill, SkillMetadata
from sgr_agent_core.tools import FinalAnswerTool, SkillTool
from tests.conftest import create_test_agent
from tests.test_agent_e2e import MockStream

pytestmark = pytest.mark.e2e


def _next_step(tool_class: Type, tool_data: dict, reasoning_data: dict):
    NextStepTools = NextStepToolsBuilder.build_NextStepTools([tool_class])
    data = tool_data.copy()
    data["tool_name_discriminator"] = tool_class.tool_name
    return NextStepTools(function=data, **reasoning_data)


def _reasoning(done: bool):
    return {
        "reasoning_steps": ["Assess task", "Decide next action"],
        "current_situation": "Working",
        "plan_status": "In progress" if not done else "Done",
        "enough_data": done,
        "remaining_steps": ["finish"] if done else ["use skill"],
        "task_completed": done,
    }


def _mock_client_use_skill_then_finish() -> AsyncOpenAI:
    """LLM first invokes use_skill(greet), then FinalAnswerTool."""
    client = Mock(spec=AsyncOpenAI)

    resp1 = _next_step(SkillTool, {"skill_name": "greet"}, _reasoning(False))
    resp2 = _next_step(
        FinalAnswerTool,
        {
            "reasoning": "Skill loaded; answering",
            "completed_steps": ["Loaded greet skill"],
            "answer": "Hello there!",
            "status": AgentStatesEnum.COMPLETED,
        },
        _reasoning(True),
    )

    calls = {"n": 0}

    def mock_stream(**kwargs):
        calls["n"] += 1
        return MockStream(final_completion_data={"parsed": resp1 if calls["n"] == 1 else resp2})

    client.chat.completions.stream = Mock(side_effect=mock_stream)
    return client


@pytest.mark.asyncio
async def test_agent_autonomously_invokes_skill():
    """The agent picks use_skill from the catalog and the skill body enters the
    conversation before it finishes."""
    skill = Skill(
        metadata=SkillMetadata(name="greet", description="Greets people warmly."),
        body="Always greet the user by name and offer help.",
    )
    client = _mock_client_use_skill_then_finish()
    agent = create_test_agent(SGRAgent, openai_client=client, toolkit=[SkillTool, FinalAnswerTool])
    agent.available_skills = [skill]
    agent._context.available_skills = [skill]

    result = await agent.execute()

    assert agent._context.state == AgentStatesEnum.COMPLETED
    # The skill body was injected into the conversation via the use_skill result.
    convo = "\n".join(str(m.get("content", "")) for m in agent.conversation)
    assert "Always greet the user by name" in convo
    assert result == "Hello there!" or agent._context.execution_result == "Hello there!"
