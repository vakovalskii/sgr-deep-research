import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from sgr_deep_research.api.models import (
    AGENT_MODEL_MAPPING,
    AgentListItem,
    AgentListResponse,
    AgentModel,
    AgentStateResponse,
    ChatCompletionRequest,
    HealthResponse,
)
from sgr_deep_research.core.agents import BaseAgent
from sgr_deep_research.core.models import AgentStatesEnum

logger = logging.getLogger(__name__)

app = FastAPI(title="SGR Deep Research API", version="1.0.0")

# ToDo: better to move to a separate service
agents_storage: dict[str, BaseAgent] = {}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.get("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def get_agent_state(agent_id: str):
    if agent_id not in agents_storage:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = agents_storage[agent_id]

    current_state_dict = None
    if agent._context.current_state_reasoning:
        current_state_dict = agent._context.current_state_reasoning.model_dump()

    return AgentStateResponse(
        agent_id=agent.id,
        task=agent.task,
        state=agent.state.value,
        searches_used=agent._context.searches_used,
        clarifications_used=agent._context.clarifications_used,
        sources_count=len(agent._context.sources),
        current_state=current_state_dict,
    )


@app.get("/agents", response_model=AgentListResponse)
async def get_agents_list():
    agents_list = [
        AgentListItem(agent_id=agent.id, task=agent.task, state=agent.state.value) for agent in agents_storage.values()
    ]

    return AgentListResponse(agents=agents_list, total=len(agents_list))


@app.get("/v1/models")
async def get_available_models():
    """Get list of available agent models."""
    return {
        "data": [
            {"id": model.value, "object": "model", "created": 1234567890, "owned_by": "sgr-deep-research"}
            for model in AgentModel
        ],
        "object": "list",
    }


def extract_user_content_from_messages(messages):
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    raise ValueError("User message not found in messages")


@app.post("agents/{agent_id}/provide_clarification")
async def provide_clarification(agent_id: str, request: ChatCompletionRequest):
    if not request.stream:
        raise HTTPException(status_code=501, detail="Only streaming responses are supported. Set 'stream=true'")

    try:
        clarifications_content = extract_user_content_from_messages(request.messages)
        agent = agents_storage.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        logger.info(f"Providing clarification to agent {agent.id}: {clarifications_content[:100]}...")

        await agent.provide_clarification(clarifications_content)
        return StreamingResponse(
            agent.streaming_generator.stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Agent-ID": str(agent.id),
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _is_agent_id(model_str: str) -> bool:
    """Check if model string is an agent ID (contains underscore and UUID-like
    format)."""
    return "_" in model_str and len(model_str) > 20


@app.post("/v1/chat/completions")
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
        return await provide_clarification(request.model, request)

    try:
        task = extract_user_content_from_messages(request.messages)

        # Determine agent model type
        agent_model = request.model
        if isinstance(agent_model, str) and _is_agent_id(agent_model):
            # If it's an agent ID but not found in storage, use default
            agent_model = AgentModel.SGR_AGENT
        elif agent_model is None:
            agent_model = AgentModel.SGR_AGENT
        elif isinstance(agent_model, str):
            # Try to convert string to AgentModel enum
            try:
                agent_model = AgentModel(agent_model)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid model '{agent_model}'. Available models: {[m.value for m in AgentModel]}",
                )

        # Create agent using mapping
        agent_class = AGENT_MODEL_MAPPING[agent_model]
        agent = agent_class(task=task)
        agents_storage[agent.id] = agent
        logger.info(f"Agent {agent.id} ({agent_model.value}) created and stored for task: {task[:100]}...")

        _ = asyncio.create_task(agent.execute())
        return StreamingResponse(
            agent.streaming_generator.stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Agent-ID": str(agent.id),
                "X-Agent-Model": agent_model.value,
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))
