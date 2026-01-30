"""Dialog agent for long-running conversations with intermediate results."""

from typing import Type

from openai import AsyncOpenAI

from sgr_agent_core.agent_definition import AgentConfig
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import AnswerTool, BaseTool
from sgr_agent_core.agents.sgr_tool_calling_agent import SGRToolCallingAgent


class DialogAgent(SGRToolCallingAgent):
    """Agent specialized for dialog interactions with intermediate results.

    Uses AnswerTool to share intermediate results and maintain conversation flow,
    keeping the agent available for further interactions. Supports long dialogs
    with full conversation history.
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
        # Ensure AnswerTool is in toolkit for dialog flow; keep tools from config/registry
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

    async def _after_action_phase(self, action_tool: BaseTool, result: str) -> None:
        """Wait for user response when AnswerTool was used."""
        await super()._after_action_phase(action_tool, result)
        if isinstance(action_tool, AnswerTool):
            self.logger.info("\n💬 Dialog shared - agent waiting for response")
            self._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
            self.streaming_generator.finish(result)
            self._context.clarification_received.clear()
            await self._context.clarification_received.wait()
