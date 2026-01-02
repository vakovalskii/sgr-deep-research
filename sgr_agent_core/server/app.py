"""FastAPI application instance creation and configuration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sgr_agent_core import AgentFactory, AgentRegistry, ToolRegistry, __version__
from sgr_agent_core.server.endpoints import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for tool in ToolRegistry.list_items():
        logger.info(f"Tool registered: {tool.__name__}")
    for agent in AgentRegistry.list_items():
        logger.info(f"Agent registered: {agent.__name__}")
    for defn in AgentFactory.get_definitions_list():
        logger.info(f"Agent definition loaded: {defn}")
    yield


app = FastAPI(title="SGR Agent Core API", version=__version__, lifespan=lifespan)
# Don't use this CORS setting in production!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
