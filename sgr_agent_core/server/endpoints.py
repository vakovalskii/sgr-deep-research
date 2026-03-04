import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from sgr_agent_core import AgentFactory, AgentStatesEnum, BaseAgent
from sgr_agent_core.server.models import (
    AgentCancelResponse,
    AgentDeleteResponse,
    AgentListItem,
    AgentListResponse,
    AgentStateResponse,
    ChatCompletionRequest,
    HealthResponse,
    MessagesRequest,
)
from sgr_agent_core.utils import is_agent_id

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


@router.post("/agents/{agent_id}/cancel", response_model=AgentCancelResponse)
async def cancel_agent(agent_id: str):
    """Cancel agent execution.

    If the agent is currently running, it will be cancelled.
    The agent remains in storage and can be queried later.

    Args:
        agent_id: The ID of the agent to cancel

    Returns:
        AgentCancelResponse with cancellation status and current state

    Raises:
        HTTPException: 404 if agent not found
    """
    if agent_id not in agents_storage:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = agents_storage[agent_id]

    # Cancel the agent if it's running
    await agent.cancel()

    # Get current state after cancellation
    current_state = agent._context.state.value

    logger.info(f"Agent {agent_id} cancelled with state: {current_state}")

    return AgentCancelResponse(
        agent_id=agent_id,
        cancelled=True,
        state=current_state,
    )


@router.delete("/agents/{agent_id}", response_model=AgentDeleteResponse)
async def delete_agent(agent_id: str):
    """Delete (cancel) an agent and remove it from storage.

    If the agent is currently running, it will be cancelled first.
    The agent is then removed from storage.

    Args:
        agent_id: The ID of the agent to delete

    Returns:
        AgentDeleteResponse with deletion status and final state

    Raises:
        HTTPException: 404 if agent not found
    """
    if agent_id not in agents_storage:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = agents_storage[agent_id]

    # Cancel the agent if it's running
    await agent.cancel()

    # Get final state before removing from storage
    final_state = agent._context.state.value

    # Remove from storage
    del agents_storage[agent_id]
    logger.info(f"Agent {agent_id} deleted with final state: {final_state}")

    return AgentDeleteResponse(
        agent_id=agent_id,
        deleted=True,
        final_state=final_state,
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
async def provide_clarification(
    request: MessagesRequest,
    agent_id: str,
) -> StreamingResponse:
    messages = list(request.messages.root)
    agent = agents_storage.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        await agent.provide_clarification(messages, replace_conversation=request.agent_id_from_messages is not None)
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


@router.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    if not request.stream:
        raise HTTPException(status_code=501, detail="Only streaming responses are supported. Set 'stream=true'")

    agent_id = request.agent_id_from_messages or (request.model if is_agent_id(request.model) else None)
    if (
        agent_id is not None
        and agent_id in agents_storage
        and agents_storage[agent_id]._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION
    ):
        response = await provide_clarification(request, agent_id=agent_id)
        return response

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
        asyncio.create_task(agent.execute())
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
