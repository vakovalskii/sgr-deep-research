"""
Open-WebUI compatible adapter for SGRToolCallingAgent.
Inherits from the library class and overrides streaming methods to fix:
1. Duplicate tool calls - LLM and agent send identical tool calls with index=0
2. FinalAnswerTool sends full JSON instead of just the answer
3. Uses HTML <details> tags for tool call display in Open-WebUI
"""
import logging
from typing import Type

from openai import AsyncOpenAI, pydantic_function_tool

from sgr_agent_core.agent_config import AgentConfig
from sgr_agent_core.agents.sgr_tool_calling_agent import SGRToolCallingAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import BaseTool
from sgr_deep_research.adapters.streaming import OpenWebUIStreamingGenerator
from sgr_deep_research.adapters.tools import FinalAnswerToolOWUI, ReasoningToolOWUI

logger = logging.getLogger(__name__)


class OpenWebUIToolCallingAgent(SGRToolCallingAgent):
    """
    Adapter for SGRToolCallingAgent to work with Open-WebUI.

    Fixes:
    1. Filters duplicate tool calls from LLM (prevents JSON concatenation errors)
    2. Sends only clean answer for FinalAnswerTool (instead of full JSON)
    3. Uses HTML <details> tags for better tool call display
    """

    name: str = "openwebui_tool_calling_agent"

    def __init__(
        self,
        task: str,
        openai_client: AsyncOpenAI,
        agent_config: AgentConfig,
        toolkit: list[Type[BaseTool]],
        def_name: str | None = None,
        **kwargs: dict,
    ):
        super().__init__(
            task=task,
            openai_client=openai_client,
            agent_config=agent_config,
            toolkit=toolkit,
            def_name=def_name,
            **kwargs,
        )
        # Replace base streaming generator with Open-WebUI specific one
        self.streaming_generator = OpenWebUIStreamingGenerator(model=self.id)
        self._stream_finished = False
    
    async def _generate_final_answer_streaming(self) -> None:
        """Generate final answer using LLM completion without tools."""
        from sgr_agent_core.services.prompt_loader import PromptLoader
        
        # Prepare messages for final answer generation
        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant. Based on the conversation history, "
                           "provide a comprehensive and accurate final answer to the user's question. "
                           "Be concise, factual, and directly address what was asked."
            },
            *self.conversation,
        ]
        
        logger.info(f"🎯 Generating final answer via LLM completion")
        
        try:
            # Stream the final answer from LLM
            stream = await self.openai_client.chat.completions.create(
                model=self.config.llm.model,
                messages=messages,
                max_tokens=self.config.llm.max_tokens,
                temperature=self.config.llm.temperature,
                stream=True,
            )
            
            full_response = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    self.streaming_generator.add_chunk_from_str(content)
            
            # Save to context
            self._context.execution_result = full_response
            
            # Add to conversation
            self.conversation.append({
                "role": "assistant",
                "content": full_response
            })
            
            logger.info(f"✅ Final answer generated: {full_response[:150]}...")
            
        except Exception as e:
            logger.error(f"❌ Error generating final answer: {e}")
            error_message = "Sorry, an error occurred while generating the final answer."
            self.streaming_generator.add_chunk_from_str(error_message)
            self._context.execution_result = error_message

    async def _reasoning_phase(self) -> ReasoningToolOWUI:
        """Override: don't stream LLM chunks, only send final <details> tag."""
        async with self.openai_client.chat.completions.stream(
            messages=await self._prepare_context(),
            tools=[pydantic_function_tool(ReasoningToolOWUI, name="reasoning")],
            tool_choice={"type": "function", "function": {"name": "reasoning"}},
            **self.config.llm.to_openai_client_kwargs(),
        ) as stream:
            # DON'T stream LLM chunks - we'll send our own <details> tag
            # Just consume the stream to get the final result
            reasoning: ReasoningToolOWUI = (
                (await stream.get_final_completion()).choices[0].message.tool_calls[0].function.parsed_arguments
            )

        # ReasoningTool: arguments ARE the result (no separate execute)
        # Send reasoning as text chunk BEFORE details tag (like in history branch)
        tool_call_id = f"{self._context.iteration}-reasoning"
        logger.info(f"✅ Sending REASONING tool call (arguments = result): {tool_call_id}")
        
        # Extract reasoning text and send as regular text chunk
        reasoning_text = reasoning.reasoning if hasattr(reasoning, 'reasoning') else "Reasoning complete"
        self.streaming_generator.add_chunk_from_str(f"💭 {reasoning_text}\n\n")
        
        # Then send details tag with full JSON
        self.streaming_generator.add_tool_call_with_result(
            tool_call_id,
            reasoning.tool_name,
            reasoning.model_dump_json(),  # Full JSON in arguments for debugging
            "Reasoning complete",  # Simple result text
            reasoning=reasoning_text  # Reasoning in attribute
        )

        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "id": tool_call_id,
                        "function": {
                            "name": reasoning.tool_name,
                            "arguments": reasoning.model_dump_json(),
                        },
                    }
                ],
            }
        )

        tool_call_result = await reasoning(self._context)
        
        self.conversation.append(
            {"role": "tool", "content": tool_call_result, "tool_call_id": tool_call_id}
        )
        # Log reasoning with OWUI-specific fields
        self._log_reasoning_owui(reasoning)
        return reasoning
    
    def _log_reasoning_owui(self, result: ReasoningToolOWUI) -> None:
        """Override logging for ReasoningToolOWUI with its specific fields."""
        next_step = result.remaining_steps[0] if result.remaining_steps else "Completing"
        logger.info(
            f"""
    ###############################################
    🤖 LLM RESPONSE DEBUG:
       💭 Reasoning: {result.reasoning}
       📊 Current Situation: {result.current_situation}
       📋 Plan Status: {result.plan_status}
       ✅ Enough Data: {result.enough_data}
       📝 Remaining Steps: {result.remaining_steps}
       🏁 Task Completed: {result.task_completed}
       ➡️ Next Step: {next_step}
    ###############################################"""
        )

    async def _select_action_phase(self, reasoning: ReasoningToolOWUI) -> BaseTool:
        """Override: don't stream LLM chunks, only send final <details> tag."""
        async with self.openai_client.chat.completions.stream(
            messages=await self._prepare_context(),
            tools=await self._prepare_tools(),
            tool_choice=self.tool_choice,
            **self.config.llm.to_openai_client_kwargs(),
        ) as stream:
            # DON'T stream LLM chunks - we'll send our own <details> tag
            # Just consume the stream to get the final result
            completion = await stream.get_final_completion()

        try:
            tool = completion.choices[0].message.tool_calls[0].function.parsed_arguments
        except (IndexError, AttributeError, TypeError):
            final_content = completion.choices[0].message.content or "Task completed successfully"
            tool = FinalAnswerToolOWUI(
                reasoning="Agent decided to complete the task",
                ready_to_answer=True,
            )

        if not isinstance(tool, BaseTool):
            raise ValueError("Selected tool is not a valid BaseTool instance")

        tool_call_id = f"{self._context.iteration}-action"
        
        # Check if tool has real execute logic (will return different result than arguments)
        tools_with_execute = ["websearchtool", "extractpagecontenttool"]
        has_execute = tool.tool_name.lower() in tools_with_execute
        
        # For FinalAnswerToolOWUI, DON'T send any details tag
        # We'll generate the final answer via streaming completion
        if isinstance(tool, FinalAnswerToolOWUI):
            logger.info(f"🎯 FinalAnswerToolOWUI selected, will generate streaming answer")
            # Don't send any details tag - just prepare for streaming completion
        elif has_execute:
            # For tools with execute logic, send done="false" (execution starting)
            logger.info(f"📤 Sending ACTION tool call START (done=false): {tool_call_id} ({tool.tool_name})")
            self.streaming_generator.add_tool_call_start(
                tool_call_id,
                tool.tool_name,
                tool.model_dump_json()
            )
            logger.info(f"✅ START sent successfully, tool will execute in _action_phase")
        else:
            # For other tools (arguments = result), send done="true" immediately
            logger.info(f"✅ Sending ACTION tool call (arguments = result): {tool_call_id} ({tool.tool_name})")
            self.streaming_generator.add_tool_call_with_result(
                tool_call_id,
                tool.tool_name,
                tool.model_dump_json(),
                tool.model_dump_json()
            )

        self.conversation.append(
            {
                "role": "assistant",
                "content": reasoning.remaining_steps[0] if reasoning.remaining_steps else "Completing",
                "tool_calls": [
                    {
                        "type": "function",
                        "id": tool_call_id,
                        "function": {
                            "name": tool.tool_name,
                            "arguments": tool.model_dump_json(),
                        },
                    }
                ],
            }
        )

        return tool

    async def _action_phase(self, tool: BaseTool) -> str:
        """Override: send only clean answer for FinalAnswerTool and finish stream."""
        tool_call_id = f"{self._context.iteration}-action"
        
        # Check if tool has real execute logic
        tools_with_execute = ["websearchtool", "extractpagecontenttool"]
        has_execute = tool.tool_name.lower() in tools_with_execute
        
        logger.info(f"🔧 Executing tool: {tool.tool_name} (has_execute={has_execute})")
        result = await tool(self._context, self.config)
        logger.info(f"✅ Tool executed, result length: {len(result)} chars")
        
        # Only send RESULT for tools with execute (others already sent in _select_action_phase)
        if has_execute:
            logger.info(f"📤 Sending ACTION tool call RESULT (done=true): {tool_call_id}")
            self.streaming_generator.add_tool_call_with_result(
                tool_call_id,
                tool.tool_name,
                tool.model_dump_json(),
                result
            )
            logger.info(f"✅ Result sent successfully")
        
        self.conversation.append(
            {"role": "tool", "content": result, "tool_call_id": tool_call_id}
        )

        # For FinalAnswerToolOWUI, generate final answer via LLM completion
        if isinstance(tool, FinalAnswerToolOWUI) and tool.ready_to_answer:
            logger.info(f"✅ FinalAnswerToolOWUI triggered, generating final answer via LLM")
            
            # Generate final answer using LLM completion without tools
            await self._generate_final_answer_streaming()
            
            # Finish stream
            self.streaming_generator.finish(content=None, finish_reason="stop")
            self._stream_finished = True
            
            # Save log before exiting
            self._save_agent_log()
            
            # CRITICAL: Just return - state is COMPLETED so loop will exit naturally
            self._log_tool_execution(tool, result)
            return result
        else:
            logger.debug(f"Tool result: {tool.tool_name} - {result[:100]}...")

        self._log_tool_execution(tool, result)
        return result
    
    async def execute(self):
        """Override execute to prevent double finish() call."""
        try:
            result = await super().execute()
            return result
        finally:
            # Only call finish() if we haven't already done it
            if not self._stream_finished and self.streaming_generator is not None:
                logger.debug("Calling finish() in finally block")
                self.streaming_generator.finish(self._context.execution_result)
