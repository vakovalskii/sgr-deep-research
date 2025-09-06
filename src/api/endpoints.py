import asyncio
import logging

from core.agent import SGRResearchAgent
from core.models import AgentStatesEnum
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from settings import get_config

from api.models import AgentListItem, AgentListResponse, AgentStateResponse, ChatCompletionRequest, HealthResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="SGR Deep Research API", version="1.0.0")

# ToDo: better to move to a separate service
agents_storage: dict[str, SGRResearchAgent] = {}
config = get_config().app_config


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.get("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def get_agent_state(agent_id: str):
    if agent_id not in agents_storage:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = agents_storage[agent_id]

    current_state_dict = None
    if agent._context.current_state:
        current_state_dict = agent._context.current_state.model_dump()

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
        raise HTTPException(status_code=500, detail="str(e)")


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    if not request.stream:
        raise HTTPException(status_code=501, detail="Only streaming responses are supported. Set 'stream=true'")
    if (
        request.model
        and request.model in agents_storage
        and agents_storage[request.model].state == AgentStatesEnum.WAITING_FOR_CLARIFICATION
    ):
        return await provide_clarification(request.model, request)
    try:
        task = extract_user_content_from_messages(request.messages)
        agent = SGRResearchAgent(task=task, config=config)

        agents_storage[agent.id] = agent
        logger.info(f"Agent {agent.id} created and stored for task: {task[:100]}...")

        _ = asyncio.create_task(agent.execute())
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
        raise HTTPException(status_code=500, detail="str(e)")
