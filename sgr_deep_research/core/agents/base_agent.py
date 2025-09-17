import json
import logging
import os
import traceback
import uuid
from datetime import datetime
from typing import Type

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_deep_research.core.models import AgentStatesEnum, ResearchContext
from sgr_deep_research.core.prompts import PromptLoader
from sgr_deep_research.core.stream import OpenAIStreamingGenerator
from sgr_deep_research.core.tools import (
    # Base
    BaseTool,
    ClarificationTool,
    ReasoningTool,
    system_agent_tools,
)
from sgr_deep_research.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

config = get_config()
logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for agents."""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        max_iterations: int | None = None,
        max_clarifications: int = 3,
    ):
        self.id = f"base_agent_{uuid.uuid4()}"
        self.task = task
        self.toolkit = [*system_agent_tools, *(toolkit or [])]

        self._context = ResearchContext()
        self.conversation = []
        self.log = []
        self.max_iterations = max_iterations or config.execution.max_steps
        self.max_clarifications = max_clarifications

        client_kwargs = {"base_url": config.openai.base_url, "api_key": config.openai.api_key}
        if config.openai.proxy.strip():
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=config.openai.proxy)

        self.openai_client = AsyncOpenAI(**client_kwargs)
        self.streaming_generator = OpenAIStreamingGenerator(model=self.id)

    async def provide_clarification(self, clarifications: str):
        """Receive clarification from external source (e.g. user input)"""
        self.conversation.append({"role": "user", "content": f"CLARIFICATIONS: {clarifications}"})
        self._context.clarifications_used += 1
        self._context.clarification_received.set()
        self._context.state = AgentStatesEnum.RESEARCHING
        logger.info(f"✅ Clarification received: {clarifications[:2000]}...")

    def _log_reasoning(self, result: ReasoningTool) -> None:
        next_step = result.remaining_steps[0] if result.remaining_steps else "Completing"
        logger.info(
            f"""
###############################################
🤖 LLM RESPONSE DEBUG:
   🧠 Reasoning Steps: {result.reasoning_steps}
   📊 Current Situation: '{result.current_situation[:400]}...'
   📋 Plan Status: '{result.plan_status[:400]}...'
   🔍 Searches Done: {self._context.searches_used}
   🔍 Clarifications Done: {self._context.clarifications_used}
   ✅ Enough Data: {result.enough_data}
   📝 Remaining Steps: {result.remaining_steps}
   🏁 Task Completed: {result.task_completed}
   ➡️ Next Step: {next_step}
###############################################"""
        )
        self.log.append(
            {
                "step_number": self._context.iteration,
                "timestamp": datetime.now().isoformat(),
                "step_type": "reasoning",
                "agent_reasoning": result.model_dump(),
            }
        )

    def _log_tool_execution(self, tool: BaseTool, result: str):
        logger.info(
            f"""
###############################################
🛠️ TOOL EXECUTION DEBUG:
   🔧 Tool Name: {tool.tool_name}
   📋 Tool Model: {tool.model_dump_json(indent=2)}
###############################################"""
        )
        self.log.append(
            {
                "step_number": self._context.iteration,
                "timestamp": datetime.now().isoformat(),
                "step_type": "tool_execution",
                "tool_name": tool.tool_name,
                "agent_tool_context": tool.model_dump(),
                "agent_tool_execution_result": result,
            }
        )

    def _log_openai_request(self, request_data: dict, response_info: dict | None = None):
        """Log OpenAI API request and response information."""
        logger.info(
            f"""
###############################################
🤖 OPENAI API CALL DEBUG:
   🔧 Model: {config.openai.model}
   📋 Request: {json.dumps(request_data, indent=2, ensure_ascii=False)[:1000]}...
   📊 Base URL: {config.openai.base_url}
   🌡️ Temperature: {config.openai.temperature}
   🔢 Max Tokens: {config.openai.max_tokens}
###############################################"""
        )
        self.log.append(
            {
                "step_number": self._context.iteration,
                "timestamp": datetime.now().isoformat(),
                "step_type": "openai_request",
                "model_info": {
                    "model": config.openai.model,
                    "base_url": config.openai.base_url,
                    "temperature": config.openai.temperature,
                    "max_tokens": config.openai.max_tokens,
                    "proxy": config.openai.proxy if config.openai.proxy.strip() else None,
                },
                "raw_request": request_data,
                "response_info": response_info,
            }
        )

    def _save_agent_log(self):
        logs_dir = config.execution.logs_dir
        os.makedirs(logs_dir, exist_ok=True)
        filepath = os.path.join(logs_dir, f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{self.id}-log.json")
        agent_log = {
            "id": self.id,
            "task": self.task,
            "model_info": {
                "model": config.openai.model,
                "base_url": config.openai.base_url,
                "temperature": config.openai.temperature,
                "max_tokens": config.openai.max_tokens,
                "proxy": config.openai.proxy if config.openai.proxy.strip() else None,
            },
            "context": self._context.agent_state(),
            "log": self.log,
        }

        json.dump(agent_log, open(filepath, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    async def _prepare_context(self) -> list[dict]:
        """Prepare conversation context with system prompt."""
        system_prompt = PromptLoader.get_system_prompt(
            user_request=self.task,
            sources=list(self._context.sources.values()),
            available_tools=self.toolkit,
            previous_searches_summary=self._context.previous_searches_summary,
        )
        return [{"role": "system", "content": system_prompt}, *self.conversation]

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for current agent state and progress."""
        raise NotImplementedError("_prepare_tools must be implemented by subclass")

    async def _reasoning_phase(self) -> ReasoningTool:
        """Call LLM to decide next action based on current context."""
        raise NotImplementedError("_reasoning_phase must be implemented by subclass")

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
        """Select most suitable tool for the action decided in reasoning phase.

        Returns the tool suitable for the action.
        """
        raise NotImplementedError("_select_action_phase must be implemented by subclass")

    async def _action_phase(self, tool: BaseTool) -> str:
        """Call Tool for the action decided in select_action phase.

        Returns string or dumped json result of the tool execution.
        """
        raise NotImplementedError("_action_phase must be implemented by subclass")

    async def execute(
        self,
    ):
        logger.info(f"🚀 Starting agent {self.id} for task: '{self.task}'")
        self.conversation.extend(
            [
                {
                    "role": "user",
                    "content": f"\nORIGINAL USER REQUEST: '{self.task}'\n",
                }
            ]
        )
        try:
            while self._context.state not in AgentStatesEnum.FINISH_STATES.value:
                self._context.iteration += 1
                logger.info(f"agent {self.id} Step {self._context.iteration} started")

                # Enforce max_iterations limit
                if self._context.iteration > self.max_iterations:
                    logger.warning(f"⚠️ Agent {self.id} reached max iterations ({self.max_iterations}), forcing completion")
                    self._context.state = AgentStatesEnum.COMPLETED
                    break

                reasoning = await self._reasoning_phase()
                self._context.current_state_reasoning = reasoning
                action_tool = await self._select_action_phase(reasoning)
                action_result = await self._action_phase(action_tool)

                if isinstance(action_tool, ClarificationTool):
                    logger.info("\n⏸️  Research paused - please answer questions")
                    logger.info(action_result)
                    self._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
                    self._context.clarification_received.clear()
                    await self._context.clarification_received.wait()
                    continue

        except Exception as e:
            logger.error(f"❌ Agent execution error: {str(e)}")
            self._context.state = AgentStatesEnum.FAILED
            traceback.print_exc()
        finally:
            if self.streaming_generator is not None:
                self.streaming_generator.finish()
            self._save_agent_log()
