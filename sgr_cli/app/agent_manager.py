"""Agent management and execution."""

import asyncio
import inspect
import json
import logging
from typing import Optional

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.services import ToolRegistry
from sgr_agent_core.stream import OpenAIStreamingGenerator

from .models import AgentState, Message, ToolExecution
from .utils import format_image_for_openai

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages agent lifecycle and execution."""

    def __init__(self, config: GlobalConfig, agent_name: Optional[str] = None):
        """Initialize agent manager.

        Args:
            config: Global configuration
            agent_name: Name of agent to use. If None, uses first available agent.
        """
        self.config = config
        self.agent: Optional[BaseAgent] = None
        self.agent_name = agent_name or self._get_default_agent_name()
        self.current_state = AgentState.IDLE
        self.tool_executions: list[ToolExecution] = []
        self.streaming_content = ""

    def _get_default_agent_name(self) -> str:
        """Get default agent name from config."""
        if not self.config.agents:
            raise ValueError("No agents configured")
        return list(self.config.agents.keys())[0]

    async def create_agent(self, task_messages: list[ChatCompletionMessageParam]) -> BaseAgent:
        """Create and initialize agent.

        Args:
            task_messages: Initial task messages (can include multimodal content)

        Returns:
            Created agent instance
        """
        if self.agent_name not in self.config.agents:
            raise ValueError(f"Agent '{self.agent_name}' not found in config")

        agent_def = self.config.agents[self.agent_name]
        
        # Check if agent base class requires 'task' instead of 'task_messages'
        # ResearchSGRAgent and similar classes need 'task' as first positional argument
        base_class = agent_def.base_class
        if base_class is not None:
            # Get class name - handle both class objects and string references
            if isinstance(base_class, str):
                class_name = base_class.split('.')[-1]  # Extract class name from module path
            else:
                class_name = getattr(base_class, '__name__', str(base_class))
            
            logger.debug(f"Checking agent base class: {class_name} (type: {type(base_class)})")
            
            # Check by class name first (more reliable)
            if 'ResearchSGRAgent' in class_name or 'Research' in class_name and 'SGR' in class_name:
                # This agent requires 'task' string instead of 'task_messages'
                logger.debug(f"Detected ResearchSGRAgent, extracting task text")
                task_text = self._extract_task_text(task_messages)
                if not task_text:
                    raise ValueError("Cannot extract task text from messages")
                logger.debug(f"Creating ResearchSGRAgent with task: {task_text[:50]}...")
                self.agent = await self._create_research_agent(agent_def, task_text)
                self.current_state = AgentState.IDLE
                return self.agent
            
            # Also check by signature as fallback (only if base_class is actually a class)
            if not isinstance(base_class, str):
                try:
                    sig = inspect.signature(base_class.__init__)
                    params = list(sig.parameters.keys())
                    logger.debug(f"Signature parameters: {params}")
                    # Skip 'self' parameter
                    if len(params) > 1 and params[1] == 'task':
                        # This agent requires 'task' string instead of 'task_messages'
                        logger.debug(f"Detected 'task' parameter in signature, extracting task text")
                        task_text = self._extract_task_text(task_messages)
                        if not task_text:
                            raise ValueError("Cannot extract task text from messages")
                        self.agent = await self._create_research_agent(agent_def, task_text)
                        self.current_state = AgentState.IDLE
                        return self.agent
                except (AttributeError, ValueError, TypeError) as e:
                    # If we can't inspect the signature, log and fall back to standard creation
                    logger.debug(f"Could not inspect signature for {class_name}: {e}")
        
        # Standard creation path for agents that use task_messages
        logger.debug(f"Using standard AgentFactory.create() path")
        self.agent = await AgentFactory.create(agent_def, task_messages)
        self.current_state = AgentState.IDLE
        return self.agent
    
    def _extract_task_text(self, task_messages: list[ChatCompletionMessageParam]) -> str:
        """Extract task text from task_messages.
        
        Args:
            task_messages: List of messages
            
        Returns:
            Extracted task text
        """
        if not task_messages:
            return ""
        
        # Get the last user message
        for msg in reversed(task_messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # Extract text from multimodal content
                    text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                    return " ".join(text_parts)
        
        return ""
    
    async def _create_research_agent(self, agent_def, task: str) -> BaseAgent:
        """Create ResearchSGRAgent manually with task string.
        
        Args:
            agent_def: Agent definition
            task: Task text string
            
        Returns:
            Created agent instance
        """
        # Create OpenAI client
        client_kwargs = {"base_url": agent_def.llm.base_url, "api_key": agent_def.llm.api_key}
        if agent_def.llm.proxy:
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=agent_def.llm.proxy)
        openai_client = AsyncOpenAI(**client_kwargs)
        
        # Get tools
        tools = []
        for tool in agent_def.tools:
            if isinstance(tool, str):
                tool_class = ToolRegistry.get(tool)
                if tool_class is None:
                    raise ValueError(f"Tool '{tool}' not found in registry")
            else:
                tool_class = tool
            tools.append(tool_class)
        
        # Get base class
        base_class = agent_def.base_class
        if base_class is None:
            raise ValueError(f"Base class not specified for agent '{agent_def.name}'")
        
        # ResearchSGRAgent requires 'task' but its parent SGRAgent requires 'task_messages'
        # Create a wrapper class that fixes the super().__init__() call
        class FixedResearchSGRAgent(base_class):
            """Wrapper that fixes task -> task_messages conversion for super().__init__()."""
            
            def __init__(self, task: str, openai_client, agent_config, toolkit, def_name=None, **kwargs):
                # Convert task to task_messages format
                task_messages = [{"role": "user", "content": task}]
                
                # Set up research_toolkit like ResearchSGRAgent does
                from sgr_agent_core.tools import (
                    WebSearchTool,
                    ExtractPageContentTool,
                    CreateReportTool,
                    FinalAnswerTool,
                )
                research_toolkit = [WebSearchTool, ExtractPageContentTool, CreateReportTool, FinalAnswerTool]
                # Merge research_toolkit with provided toolkit (same logic as ResearchSGRAgent)
                merged_toolkit = research_toolkit + [t for t in toolkit if t not in research_toolkit]
                
                # Get parent class (SGRAgent)
                parent_class = base_class.__bases__[0] if base_class.__bases__ else None
                
                if parent_class:
                    # Call parent's __init__ with task_messages instead of task
                    parent_class.__init__(
                        self,
                        task_messages=task_messages,
                        openai_client=openai_client,
                        agent_config=agent_config,
                        toolkit=merged_toolkit,
                        def_name=def_name,
                        **kwargs
                    )
                else:
                    # Fallback to original (shouldn't happen, but just in case)
                    super().__init__(
                        task=task,
                        openai_client=openai_client,
                        agent_config=agent_config,
                        toolkit=merged_toolkit,
                        def_name=def_name,
                        **kwargs
                    )
        
        # Create agent with task string using the fixed wrapper class
        agent = FixedResearchSGRAgent(
            task=task,
            def_name=agent_def.name,
            toolkit=tools,
            openai_client=openai_client,
            agent_config=agent_def,
        )
        
        return agent

    def prepare_message_with_images(self, content: str, images: list[str]) -> ChatCompletionMessageParam:
        """Prepare message with images in OpenAI format.

        Args:
            content: Text content
            images: List of image paths, URLs, or base64 data URIs

        Returns:
            Message in OpenAI ChatCompletionMessageParam format
        """
        if not images:
            return {"role": "user", "content": content}

        # Build content list with text and images
        content_parts = [{"type": "text", "text": content}]
        for image in images:
            image_part = format_image_for_openai(image)
            content_parts.append(image_part)

        return {"role": "user", "content": content_parts}

    async def execute_agent(self) -> str:
        """Execute agent and return final result.

        Returns:
            Final execution result
        """
        if not self.agent:
            raise RuntimeError("Agent not created. Call create_agent first.")

        self.current_state = AgentState.THINKING
        self.tool_executions.clear()
        self.streaming_content = ""

        try:
            # Start agent execution in background
            execution_task = asyncio.create_task(self.agent.execute())

            # Monitor agent state and streaming
            while not execution_task.done():
                await asyncio.sleep(0.1)
                if self.agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                    self.current_state = AgentState.WAITING_FOR_CLARIFICATION
                elif self.agent._context.state in AgentStatesEnum.FINISH_STATES.value:
                    self.current_state = AgentState.COMPLETED
                    break

            result = await execution_task
            self.current_state = AgentState.COMPLETED
            return result or ""

        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            self.current_state = AgentState.ERROR
            raise

    async def provide_clarification(self, clarification: str) -> None:
        """Provide clarification to agent.

        Args:
            clarification: User clarification text
        """
        if not self.agent:
            raise RuntimeError("Agent not created")

        await self.agent.provide_clarification([{"role": "user", "content": clarification}])
        self.current_state = AgentState.THINKING

    async def stream_agent_response(self):
        """Stream agent response chunks.

        Yields:
            Chunks of agent response
        """
        if not self.agent:
            raise RuntimeError("Agent not created")

        self.current_state = AgentState.STREAMING
        if self.agent.streaming_generator:
            async for chunk in self.agent.streaming_generator.stream():
                if chunk:
                    self.streaming_content += chunk
                    yield chunk

    def get_tool_executions(self) -> list[ToolExecution]:
        """Get list of tool executions."""
        if not self.agent:
            return []

        executions = []
        for log_entry in self.agent.log:
            if log_entry.get("step_type") == "tool_execution":
                executions.append(
                    ToolExecution(
                        tool_name=log_entry.get("tool_name", "unknown"),
                        arguments=log_entry.get("agent_tool_context", {}),
                        result=log_entry.get("agent_tool_execution_result", ""),
                        iteration=log_entry.get("step_number", 0),
                    )
                )
        return executions

    def get_current_state(self) -> AgentState:
        """Get current agent state."""
        return self.current_state
