"""Dialog agent for long-running conversations with intermediate results."""

from typing import Type

from openai import AsyncOpenAI

from sgr_agent_core.agent_definition import AgentConfig
from sgr_agent_core.agents.sgr_tool_calling_agent import SGRToolCallingAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import AnswerTool, BaseTool, ClarificationTool
from sgr_agent_core.tools.answer_tool import PASS_TURN_TO_USER_KEY


class DialogAgent(SGRToolCallingAgent):
    """Agent specialized for dialog interactions with intermediate results.

    Uses AnswerTool to share intermediate results and maintain
    conversation flow, keeping the agent available for further
    interactions. Supports long dialogs with full conversation history.

    Overrides _execution_step to add _after_action_phase (not in
    BaseAgent): tools can signal pass_turn_to_user via context;
    ClarificationTool pauses for user input.
    """

    name: str = "dialog_agent"

    def __init__(
        self,
        task_messages: list,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        answer_toolkit = [AnswerTool]
        merged_toolkit = answer_toolkit + [t for t in toolkit if t is not AnswerTool]
        super().__init__(
            task_messages=task_messages,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=merged_toolkit,
            def_name=def_name,
            **kwargs,
        )

    async def _execution_step(self):
        """Run one step and handle after-action wait (ClarificationTool /
        pass_turn_to_user)."""
        reasoning = await self._reasoning_phase()
        self._context.current_step_reasoning = reasoning
        action_tool = await self._select_action_phase(reasoning)
        result = await self._action_phase(action_tool)
        await self._after_action_phase(action_tool, result)

    async def _after_action_phase(self, action_tool: BaseTool, result: str) -> None:
        """Pause for user when ClarificationTool or when tool set
        pass_turn_to_user (e.g. AnswerTool)."""
        if isinstance(action_tool, ClarificationTool):
            self._context.execution_result = result
            self.logger.info("\n⏸️  Research paused - please answer questions")
            self._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
            self.streaming_generator.finish()
            self._context.clarification_received.clear()
            await self._context.clarification_received.wait()
            return
        if self._context.custom_context and self._context.custom_context.get(PASS_TURN_TO_USER_KEY):
            self._context.custom_context[PASS_TURN_TO_USER_KEY] = False
            self._context.execution_result = result
            self.logger.info("\n💬 Dialog shared - agent waiting for response")
            self._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
            self.streaming_generator.finish(result)
            self._context.clarification_received.clear()
            await self._context.clarification_received.wait()
