import asyncio
import logging
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai.types.chat import ChatCompletionMessageParam

from sgr_agent_core import AgentFactory, AgentStatesEnum, BaseAgent
from sgr_agent_core.server.models import (
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

    # Extract user context from conversation if available
    user_context = None
    if hasattr(agent, "conversation") and agent.conversation:
        user_context = [msg for msg in agent.conversation if isinstance(msg, dict) and msg.get("role") == "user"]

    return AgentStateResponse(
        agent_id=agent.id,
        task=agent.task,
        user_context=user_context,
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


def extract_user_content_from_messages(messages: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
    """Extract all last consecutive user messages (text and images), returning
    them in ChatCompletionMessageParam format."""
    if not messages:
        return []

    collected: List[ChatCompletionMessageParam] = []

    # get user content from end massive
    for msg in reversed(messages):
        # ChatCompletionMessageParam can be a dict, so we need to handle both cases
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        if role == "user":
            collected.append(msg)
        else:
            break

    # return in normal order (reverse() returns None, so we need to reverse the list)
    return list(reversed(collected))


@router.post("/agents/{agent_id}/provide_clarification")
async def provide_clarification(agent_id: str, request: ClarificationRequest):
    try:
        agent = agents_storage.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        clarifications_preview = (
            request.clarifications[:100]
            if isinstance(request.clarifications, str)
            else f"{len(request.clarifications)} parts (multimodal)"
        )
        logger.info(f"Providing clarification to agent {agent.id}: {clarifications_preview}...")

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
async def create_chat_completion(request: ChatCompletionRequest):
    if not request.stream:
        raise HTTPException(status_code=501, detail="Only streaming responses are supported. Set 'stream=true'")

    # Check if this is a clarification request for an existing agent
    if (
        request.model
        and isinstance(request.model, str)
        and _is_agent_id(request.model)
        and request.model in agents_storage
        and agents_storage[request.model]._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION
    ):
        # Extract user messages and convert to ClarificationRequest format
        user_messages = extract_user_content_from_messages(request.messages)
        if not user_messages:
            raise HTTPException(status_code=400, detail="No user messages found")

        # Convert messages to clarifications format (string or list of content parts)
        clarifications_content = []
        for msg in user_messages:
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if isinstance(content, str):
                clarifications_content.append({"type": "text", "text": content})
            elif isinstance(content, list):
                clarifications_content.extend(content)

        # If single text part, return as string; otherwise return list
        if len(clarifications_content) == 1 and clarifications_content[0].get("type") == "text":
            clarifications = clarifications_content[0].get("text", "")
        else:
            clarifications = clarifications_content

        return await provide_clarification(
            agent_id=request.model,
            request=ClarificationRequest(clarifications=clarifications),
        )

    try:
        task_messages = extract_user_content_from_messages(request.messages)

        # Extract text-only summary for agent.task
        text_parts = []
        for msg in task_messages:
            # ChatCompletionMessageParam can be a dict, so we need to handle both cases
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        if part.get("text"):
                            text_parts.append(part["text"])

        task = " ".join(text_parts).strip() if text_parts else "Image-only request"

        # Process all messages: ChatCompletionMessageParam is already a dict or compatible format
        processed_messages = []
        for msg in request.messages:
            # ChatCompletionMessageParam can be a dict, so we need to handle both cases
            if isinstance(msg, dict):
                processed_messages.append(
                    {
                        "role": msg.get("role"),
                        "content": msg.get("content"),
                    }
                )
            else:
                processed_messages.append(
                    {
                        "role": getattr(msg, "role", None),
                        "content": getattr(msg, "content", None),
                    }
                )

        agent_def = next(filter(lambda ad: ad.name == request.model, AgentFactory.get_definitions_list()), None)
        if not agent_def:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model '{request.model}'. "
                f"Available models: {[ad.name for ad in AgentFactory.get_definitions_list()]}",
            )
        agent = await AgentFactory.create(agent_def, task)
        logger.info(f"Created agent '{request.model}' for task: {task[:100]}...")

        # Add all processed messages to agent conversation (excluding system, which is added by _prepare_context)
        for msg in processed_messages:
            if msg["role"] != "system":
                agent.conversation.append(msg)

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
