import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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

    return AgentStateResponse(
        agent_id=agent.id,
        task_messages=agent.task_messages,
        sources_count=len(agent._context.sources),
        **agent._context.model_dump(),
    )


@router.get("/agents", response_model=AgentListResponse)
async def get_agents_list():
    agents_list = [
        AgentListItem(
            agent_id=agent.id,
            task_messages=agent.task_messages,
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


@router.post("/agents/{agent_id}/provide_clarification")
async def provide_clarification(agent_id: str, request: ClarificationRequest):
    try:
        agent = agents_storage.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        logger.info(f"Providing clarification to agent {agent.id}: {len(request.messages)} messages")

        await agent.provide_clarification(request.messages)
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
        return await provide_clarification(
            agent_id=request.model,
            request=ClarificationRequest(messages=request.messages.root),
        )

    try:
        agent_def = next(filter(lambda ad: ad.name == request.model, AgentFactory.get_definitions_list()), None)
        if not agent_def:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model '{request.model}'. "
                f"Available models: {[ad.name for ad in AgentFactory.get_definitions_list()]}",
            )
        agent = await AgentFactory.create(agent_def, request.messages.root)
        logger.info(f"Created agent '{request.model}' with {len(request.messages)} messages")

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
