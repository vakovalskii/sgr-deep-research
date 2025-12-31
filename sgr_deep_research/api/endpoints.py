import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from sgr_agent_core import AgentFactory, AgentStatesEnum, BaseAgent
from sgr_deep_research.adapters import OpenWebUIToolCallingAgent, extract_conversation_history
from sgr_deep_research.api.models import (
    AgentListItem,
    AgentListResponse,
    AgentStateResponse,
    ChatCompletionRequest,
    ClarificationRequest,
    HealthResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ToDo: better to move to a separate service
agents_storage: dict[str, BaseAgent] = {}

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@router.get("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def get_agent_state(agent_id: str):
    if agent_id not in agents_storage:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = agents_storage[agent_id]

    return AgentStateResponse(
        agent_id=agent.id,
        task=agent.task,
        sources_count=len(agent._context.sources),
        **agent._context.model_dump(),
    )


@router.get("/agents", response_model=AgentListResponse)
async def get_agents_list():
    agents_list = [
        AgentListItem(
            agent_id=agent.id,
            task=agent.task,
            state=agent._context.state,
            creation_time=agent.creation_time,
        )
        for agent in agents_storage.values()
    ]

    return AgentListResponse(agents=agents_list, total=len(agents_list))


@router.get("/v1/models")
async def get_available_models():
    """Get a list of available agent models."""
    models_data = [
        {
            "id": agent_def.name,
            "object": "model",
            "created": 1234567890,
            "owned_by": "sgr-agent-core",
        }
        for agent_def in AgentFactory.get_definitions_list()
    ]

    return {"data": models_data, "object": "list"}


def extract_user_content_from_messages(messages):
    """
    Extract the last user message content.
    
    For conversation continuation, this should be the NEW user message
    after the last assistant response.
    """
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    raise ValueError("User message not found in messages")


@router.post("/agents/{agent_id}/provide_clarification")
async def provide_clarification(agent_id: str, request: ClarificationRequest):
    try:
        agent = agents_storage.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        logger.info(f"Providing clarification to agent {agent.id}: {request.clarifications[:100]}...")

        await agent.provide_clarification(request.clarifications)
        return StreamingResponse(
            agent.streaming_generator.stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Agent-ID": str(agent.id),
            },
        )

    except Exception as e:
        logger.error(f"Error completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _is_agent_id(model_str: str) -> bool:
    """Check if the model string is an agent ID (contains underscore and UUID-
    like format)."""
    return "_" in model_str and len(model_str) > 20


@router.post("/v1/chat/completions")
async def create_chat_completion(http_request: Request, request: ChatCompletionRequest):
    if not request.stream:
        raise HTTPException(status_code=501, detail="Only streaming responses are supported. Set 'stream=true'")

    # Log incoming request details
    logger.info(f"Incoming request model: {request.model}")
    logger.info(f"Messages count: {len(request.messages)}")
    for idx, msg in enumerate(request.messages):
        content_preview = msg.content[:100] if msg.content else ""
        logger.info(f"[{idx}] role={msg.role}, content={content_preview}...")

    # Check if this is a clarification request for an existing agent
    if (
        request.model
        and isinstance(request.model, str)
        and _is_agent_id(request.model)
        and request.model in agents_storage
        and agents_storage[request.model]._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION
    ):
        return await provide_clarification(
            agent_id=request.model,
            request=ClarificationRequest(clarifications=extract_user_content_from_messages(request.messages)),
        )

    try:
        # Check if this is a conversation continuation (last message is not user)
        # If so, Open-WebUI is just reconnecting to the stream - ignore it
        if request.messages and request.messages[-1].role != "user":
            logger.info("⚠️  Last message is not from user - ignoring duplicate request from Open-WebUI")
            # Return empty stream that immediately closes
            async def empty_stream():
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                empty_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        
        task = extract_user_content_from_messages(request.messages)
        
        # Calculate original size before filtering
        original_size = sum(len(msg.content or "") for msg in request.messages if msg.role == "assistant")
        
        # Extract conversation history (filters out tool calls and intermediate steps)
        conversation_history = extract_conversation_history(request.messages)
        
        # Calculate filtered size
        filtered_size = sum(len(msg["content"]) for msg in conversation_history if msg["role"] == "assistant")
        
        logger.info(f"📝 Extracted task: {task[:200]}...")
        logger.info(f"📚 Conversation history: {len(conversation_history)} messages")
        if original_size > 0:
            reduction_pct = ((original_size - filtered_size) / original_size) * 100
            logger.info(f"💾 Context size reduction: {original_size} → {filtered_size} chars ({reduction_pct:.1f}% saved)")
        
        if len(conversation_history) > 1:
            logger.info("💬 Filtered conversation history (final answers only):")
            for i, msg in enumerate(conversation_history):
                logger.info(f"  [{i}] {msg['role']}: {msg['content'][:150]}...")

        agent_def = next(filter(lambda ad: ad.name == request.model, AgentFactory.get_definitions_list()), None)
        if not agent_def:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model '{request.model}'. "
                f"Available models: {[ad.name for ad in AgentFactory.get_definitions_list()]}",
            )
        
        agent = await AgentFactory.create(agent_def, task)
        
        # Inject conversation history into agent BEFORE execution to preserve context
        if len(conversation_history) > 0:
            # Check if history contains last user message with current task
            if (conversation_history[-1]["role"] == "user" and 
                conversation_history[-1]["content"].strip() == task.strip()):
                # Last message matches current task - use entire history as-is
                # Task will NOT be added in _prepare_context() since it's already in history
                logger.info(f"📜 Injecting {len(conversation_history)} historical messages into agent conversation (including current task)")
                agent.conversation.extend(conversation_history)
                
                # Override _prepare_context() to NOT add task twice
                # Save original method for using prompts
                from sgr_agent_core.services.prompt_loader import PromptLoader
                
                async def _prepare_context_with_history():
                    """Prepare context WITHOUT adding task, since it's already in history."""
                    return [
                        {"role": "system", "content": PromptLoader.get_system_prompt(agent.toolkit, agent.config.prompts)},
                        *agent.conversation,  # History already contains current task
                    ]
                
                agent._prepare_context = _prepare_context_with_history
            else:
                # Last message does NOT match current task
                # Add history WITHOUT current task - it will be added in _prepare_context()
                logger.info(f"📜 Injecting {len(conversation_history)} historical messages into agent conversation (task will be added separately)")
                agent.conversation.extend(conversation_history)
        
        logger.info(f"✅ Created agent '{request.model}' for task: {task[:100]}...")

        agents_storage[agent.id] = agent
        _ = asyncio.create_task(agent.execute())
        
        return StreamingResponse(
            agent.streaming_generator.stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Agent-ID": str(agent.id),
                "X-Agent-Model": request.model,
            },
        )

    except ValueError as e:
        logger.error(f"Error completion: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
