"""ACP Agent protocol implementation backed by SGR AgentFactory."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AuthenticateResponse,
    CloseSessionResponse,
    HttpMcpServer,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    McpCapabilities,
    McpServerStdio,
    NewSessionResponse,
    PromptCapabilities,
    PromptResponse,
    SessionConfigOptionSelect,
    SessionConfigSelectOption,
    SessionInfo,
    SetSessionConfigOptionResponse,
    SetSessionModeResponse,
    SseMcpServer,
    TextContentBlock,
)

from sgr_agent_core import __version__
from sgr_agent_core.acp.streaming import create_acp_streaming_generator_class
from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_definition import AgentDefinition
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.models import AgentStatesEnum


def extract_prompt_text(
    prompt: list[TextContentBlock | Any],
) -> str:
    """Concatenate user-visible text from ACP prompt content blocks."""
    parts: list[str] = []
    for block in prompt:
        if isinstance(block, TextContentBlock):
            parts.append(block.text)
        elif getattr(block, "type", None) == "text" and getattr(block, "text", None):
            parts.append(str(block.text))
    return "".join(parts).strip()


@dataclass
class _ACPSession:
    """Per-session state for the ACP bridge."""

    session_id: str
    cwd: str
    agent_name: str
    model: str
    agent: BaseAgent | None = None
    execute_task: asyncio.Task | None = None


class SGRACPBridge:
    """Routes ACP JSON-RPC methods to SGR agents loaded from GlobalConfig."""

    _SUPPORTED_PROTOCOL = 1
    _AGENT_CONFIG_ID = "agent"
    _MODEL_CONFIG_ID = "model"

    def __init__(self, default_agent_name: str | None = None) -> None:
        self._default_agent_name = default_agent_name
        self._sessions: dict[str, _ACPSession] = {}
        self._client: Client | None = None

    def on_connect(self, conn: Client) -> None:
        """Store the client connection for outbound session updates."""
        self._client = conn

    def _resolve_agent_name(self) -> str:
        """Pick the default agent name from constructor arg, config, or the
        first defined agent."""
        gc = GlobalConfig()
        name = self._default_agent_name
        if not name and gc.acp and gc.acp.agent:
            name = gc.acp.agent
        if not name and gc.agents:
            name = next(iter(gc.agents.keys()))
        if not name or name not in gc.agents:
            raise ValueError(
                "No agent definition selected for ACP. Set acp.agent in config or pass default_agent_name."
            )
        return name

    def _resolve_agent_definition(self) -> AgentDefinition:
        return GlobalConfig().agents[self._resolve_agent_name()]

    def _agent_definition_for_session(self, sess: _ACPSession) -> AgentDefinition:
        """Resolve the session's agent definition and apply its model override."""
        gc = GlobalConfig()
        name = sess.agent_name if sess.agent_name in gc.agents else self._resolve_agent_name()
        agent_def = gc.agents[name]
        if sess.model and sess.model != agent_def.llm.model:
            agent_def = agent_def.model_copy(deep=True)
            agent_def.llm.model = sess.model
        return agent_def

    def _agent_names(self) -> list[str]:
        return list(GlobalConfig().agents.keys())

    def _model_choices(self) -> list[str]:
        """All selectable model ids: each agent definition's model plus any
        extra models declared under ``acp.models``, de-duplicated in order."""
        gc = GlobalConfig()
        choices: list[str] = []
        if gc.acp and gc.acp.models:
            choices.extend(gc.acp.models)
        for agent_def in gc.agents.values():
            model = agent_def.llm.model
            if model:
                choices.append(model)
        seen: set[str] = set()
        return [m for m in choices if not (m in seen or seen.add(m))]

    def _build_config_options(self, sess: _ACPSession) -> list[SessionConfigOptionSelect]:
        """Expose the active agent and model as ACP session config selectors so
        clients let the user switch them at runtime."""
        agent_option = SessionConfigOptionSelect(
            id=self._AGENT_CONFIG_ID,
            name="Agent",
            description="SGR agent definition to run",
            category="_agent",
            type="select",
            current_value=sess.agent_name,
            options=[SessionConfigSelectOption(value=name, name=name) for name in self._agent_names()],
        )
        models = self._model_choices()
        if sess.model not in models:
            models = [sess.model, *models]
        model_option = SessionConfigOptionSelect(
            id=self._MODEL_CONFIG_ID,
            name="Model",
            description="LLM model used for generation",
            category="model",
            type="select",
            current_value=sess.model,
            options=[SessionConfigSelectOption(value=model, name=model) for model in models],
        )
        return [agent_option, model_option]

    def _reset_agent_if_idle(self, sess: _ACPSession) -> None:
        """Drop the cached agent so the next turn is rebuilt with the updated
        agent/model. In-flight turns are left untouched."""
        task = sess.execute_task
        if task is not None and not task.done():
            return
        sess.agent = None
        sess.execute_task = None

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any = None,
        client_info: Any = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Negotiate protocol version and advertise agent capabilities."""
        negotiated = min(protocol_version, self._SUPPORTED_PROTOCOL)
        if negotiated < 1:
            negotiated = 1
        return InitializeResponse(
            protocol_version=negotiated,
            agent_capabilities=AgentCapabilities(
                load_session=False,
                prompt_capabilities=PromptCapabilities(
                    image=False,
                    audio=False,
                    embedded_context=True,
                ),
                mcp_capabilities=McpCapabilities(http=True, sse=False),
            ),
            agent_info=Implementation(
                name="sgr-agent-core",
                title="SGR Agent Core",
                version=__version__,
            ),
            auth_methods=[],
        )

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new session id and advertise the agent/model selectors."""
        session_id = f"sgr_{uuid.uuid4().hex}"
        agent_name = self._resolve_agent_name()
        model = GlobalConfig().agents[agent_name].llm.model
        sess = _ACPSession(session_id=session_id, cwd=cwd, agent_name=agent_name, model=model)
        self._sessions[session_id] = sess
        return NewSessionResponse(session_id=session_id, config_options=self._build_config_options(sess))

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Session restore is not supported."""
        return None

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        """Return basic metadata for active sessions."""
        sessions = [SessionInfo(session_id=s.session_id, cwd=s.cwd) for s in self._sessions.values()]
        return ListSessionsResponse(sessions=sessions)

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModeResponse | None:
        """Session modes are not used."""
        return None

    async def set_config_option(
        self,
        config_id: str,
        session_id: str,
        value: str | bool,
        **kwargs: Any,
    ) -> SetSessionConfigOptionResponse | None:
        """Switch the session's agent or model, then return the full config
        state as required by the ACP spec."""
        sess = self._sessions.get(session_id)
        if sess is None:
            raise ValueError(f"Unknown session id: {session_id}")

        if config_id == self._AGENT_CONFIG_ID:
            if not isinstance(value, str) or value not in self._agent_names():
                raise ValueError(f"Unknown agent config value: {value!r}")
            sess.agent_name = value
            self._reset_agent_if_idle(sess)
        elif config_id == self._MODEL_CONFIG_ID:
            if not isinstance(value, str) or value not in self._model_choices():
                raise ValueError(f"Unknown model config value: {value!r}")
            sess.model = value
            self._reset_agent_if_idle(sess)

        return SetSessionConfigOptionResponse(config_options=self._build_config_options(sess))

    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        """Authentication is not required for this agent."""
        return None

    async def prompt(
        self,
        prompt: list[Any],
        session_id: str,
        message_id: str | None = None,
        **kwargs: Any,
    ) -> PromptResponse:
        """Run one user turn (or continue after clarification) for the SGR
        agent."""
        if self._client is None:
            raise RuntimeError("ACP client connection is not initialized")

        sess = self._sessions.get(session_id)
        if sess is None:
            raise ValueError(f"Unknown session id: {session_id}")

        text = extract_prompt_text(prompt)
        if not text:
            return PromptResponse(stop_reason="end_turn")

        if sess.agent and sess.agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
            await sess.agent.provide_clarification(
                [{"role": "user", "content": text}],
                replace_conversation=False,
            )
            if sess.execute_task:
                return await self._wait_turn(sess.agent, sess.execute_task)
            return PromptResponse(stop_reason="refusal")

        if sess.agent is not None and sess.agent._context.state in AgentStatesEnum.FINISH_STATES.value:
            sess.agent = None
            sess.execute_task = None

        agent_def = self._agent_definition_for_session(sess)
        gen_cls = create_acp_streaming_generator_class(session_id, self._client)
        agent = await AgentFactory.create(
            agent_def,
            [{"role": "user", "content": text}],
            streaming_generator=gen_cls,
        )
        sess.agent = agent
        sess.execute_task = asyncio.create_task(agent.execute())
        assert sess.execute_task is not None
        return await self._wait_turn(agent, sess.execute_task)

    async def _wait_turn(self, agent: BaseAgent, task: asyncio.Task) -> PromptResponse:
        """Wait until the agent finishes, asks for clarification, or errors."""
        while not task.done():
            if agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                return PromptResponse(stop_reason="end_turn")
            await asyncio.sleep(0.05)

        exc = task.exception()
        if exc is not None:
            if isinstance(exc, asyncio.CancelledError):
                return PromptResponse(stop_reason="cancelled")
            return PromptResponse(stop_reason="refusal")

        return PromptResponse(stop_reason=self._map_stop_reason(agent._context.state))

    def _map_stop_reason(self, state: AgentStatesEnum) -> str:
        if state == AgentStatesEnum.CANCELLED:
            return "cancelled"
        if state in (AgentStatesEnum.FAILED, AgentStatesEnum.ERROR):
            return "refusal"
        return "end_turn"

    async def close_session(self, session_id: str, **kwargs: Any) -> CloseSessionResponse | None:
        """Explicit close is not implemented."""
        return None

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Cancel an in-flight prompt turn."""
        sess = self._sessions.get(session_id)
        if sess and sess.agent:
            await sess.agent.cancel()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Extension methods are not supported."""
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Extension notifications are ignored."""
