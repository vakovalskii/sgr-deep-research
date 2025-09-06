import logging
import traceback
import uuid
from typing import Type

import httpx
from openai import AsyncOpenAI

from core.models import AgentStatesEnum, ResearchContext
from core.prompts import PromptLoader
from core.reasoning_schemas import Clarification, ReportCompletion
from core.stream import OpenAIStreamingGenerator
from core.tools import ClarificationTool, NextStepToolsBuilder, NextStepToolStub, WebSearchTool

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Вывод в консоль
    ],
)

logger = logging.getLogger(__name__)


class SGRResearchAgent:
    def __init__(self, task: str, config, max_clarifications: int = 3, max_searches: int = 4):
        self.id = f"sgr_agent_{uuid.uuid4()}"
        self.task = task
        self.config = config

        self._context = ResearchContext()
        self.conversation: list[dict] = []
        self.max_clarifications = max_clarifications
        self.max_searches = max_searches
        # Initialize OpenAI client with optional proxy support
        client_kwargs = {
            "base_url": config.openai.base_url,
            "api_key": config.openai.api_key
        }
        
        # Add proxy if configured and not empty
        if config.openai.proxy.strip():
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=config.openai.proxy)

        self.openai_client = AsyncOpenAI(**client_kwargs)
        self.state = AgentStatesEnum.INITED
        self.streaming_generator = OpenAIStreamingGenerator(model=self.id)

    def _prepare_tools(self) -> Type[NextStepToolStub]:
        """Prepare tool classes with current context limits"""
        to_exclude: list[Type] = []
        if self._context.clarifications_used >= self.max_clarifications:
            to_exclude.append(ClarificationTool)
        if self._context.searches_used >= self.max_searches:
            to_exclude.append(WebSearchTool)
        return NextStepToolsBuilder.build_NextStepTools(exclude=to_exclude, config=self.config)

    def _prepare_context(self) -> list[dict]:
        """Prepare conversation context with system prompt and current state"""
        system_prompt = PromptLoader.get_system_prompt(
            user_request=self.task, sources=list(self._context.sources.values()), config=self.config
        )
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(self.conversation)
        return conversation

    async def _openai_streaming_request(
        self, messages: list[dict], response_format: Type[NextStepToolStub]
    ) -> NextStepToolStub | None:
        async with self.openai_client.chat.completions.stream(
            model=self.config.openai.model,
            response_format=response_format,
            messages=messages,  # type: ignore
            max_tokens=self.config.openai.max_tokens,
            temperature=self.config.openai.temperature,
        ) as stream:
            async for event in stream:
                if event.type == "chunk":
                    content = event.chunk.choices[0].delta.content
                    if content:
                        self.streaming_generator.add_chunk(content)
                    if event.chunk.choices[0].finish_reason is not None:
                        return event.snapshot.choices[0].message.parsed  # type: ignore
        return None

    async def provide_clarification(self, clarifications: str):
        """Receive clarification from external source (e.g. user input)"""
        self.conversation.append({"role": "user", "content": f"CLARIFICATIONS: {clarifications}"})
        self._context.clarifications_used += 1
        self._context.clarification_received.set()
        self.state = AgentStatesEnum.RESEARCHING
        logger.info(f"✅ Clarification received: {clarifications[:300]}...")

    def _log_step(self, result: NextStepToolStub):
        next_step = result.remaining_steps[0] if result.remaining_steps else "Completing"
        reasoning = result.function.reasoning[:500] if hasattr(result.function, "reasoning") else "No reasoning"
        tool_name = result.function.tool if hasattr(result.function, "tool") else str(type(result.function).__name__)
        sources = "\n         ".join([str(source) for source in self._context.sources.values()])
        logger.info(
            f"""
###############################################
🤖 LLM RESPONSE DEBUG:
   🧠 Reasoning Steps: {result.reasoning_steps}
   📊 Current Situation: '{result.current_situation[:100]}...'
   📋 Plan Status: '{result.plan_status[:100]}...'
   🔍 Searches Done: {self._context.searches_used}
   🔍 Clarifications Done: {self._context.clarifications_used}
   🔍  Sources: 
{sources}
   ✅ Enough Data: {result.enough_data}
   📝 Remaining Steps: {result.remaining_steps}
   🏁 Task Completed: {result.task_completed}
   🔧 Tool: {result.function}
   
   ➡️ Next Step: {next_step} using {tool_name}
   💭 Reasoning: {reasoning}...
###############################################"""
        )

    async def execute(
        self,
    ):
        """Execute research task using SGR"""
        self.conversation.extend(
            [
                {
                    "role": "user",
                    "content": f"\nORIGINAL USER REQUEST: '{self.task}'\n"
                    f"(Use this for language consistency in reports)",
                }
            ]
        )
        # Execute reasoning steps
        try:
            for i in range(self.config.execution.max_steps):
                step_id = f"step-{i + 1}"
                logger.info(f"agent {self.id} Step {step_id}")
                try:
                    response_format = self._prepare_tools()
                    result: NextStepToolStub = await self._openai_streaming_request(
                        messages=self._prepare_context(), response_format=response_format
                    )
                    if result is None:
                        logger.error("Failed to parse LLM response")
                        break
                    self._log_step(result)
                    self._context.current_state = result

                except Exception as e:
                    logger.error(f"❌ LLM request error: {str(e)}")
                    break

                next_step = result.remaining_steps[0] if result.remaining_steps else "Completing"
                self.conversation.append(
                    {
                        "role": "assistant",
                        "content": next_step,
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": str(step_id),
                                "function": {
                                    "name": result.function.tool,
                                    "arguments": result.function.model_dump_json(),
                                },
                            }
                        ],
                    }
                )
                self.streaming_generator.add_tool_call(
                    str(step_id), result.function.tool, result.function.model_dump_json()
                )

                tool_call_result = result.function(self._context, self.config)  # noqa

                self.conversation.append({"role": "tool", "content": tool_call_result, "tool_call_id": step_id})
                self.streaming_generator.add_chunk(f"{tool_call_result}\n")

                if isinstance(result.function, Clarification):
                    self.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
                    self._context.clarification_received.clear()
                    await self._context.clarification_received.wait()
                    continue
                if result.task_completed or isinstance(result.function, ReportCompletion):
                    self.state = AgentStatesEnum.COMPLETED
                    logger.info("✅ Research task completed.")
                    break
        except Exception as e:
            logger.error(f"❌ Agent execution error: {str(e)}")
            traceback.print_exc()
        finally:
            self.streaming_generator.finish()
