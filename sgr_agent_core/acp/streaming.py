"""Streaming generator that maps SGR stream events to ACP session updates."""

from __future__ import annotations

import asyncio
from typing import Any

from acp.contrib.tool_calls import ToolCallTracker
from acp.helpers import text_block, tool_content, update_agent_message_text
from acp.interfaces import Client

from sgr_agent_core.stream import BaseStreamingGenerator


def create_acp_streaming_generator_class(
    session_id: str,
    client: Client,
) -> type[BaseStreamingGenerator]:
    """Build a streaming generator class bound to an ACP session and client."""

    class ACPStreamingGenerator(BaseStreamingGenerator):
        """Forwards SGR streaming events to ACP ``session/update`` notifications."""

        name = "acp"

        def __init__(self, agent_id: str) -> None:
            super().__init__()
            self._session_id = session_id
            self._client = client
            self._tracker = ToolCallTracker()

        def _emit(self, update: Any) -> None:
            async def _send() -> None:
                await self._client.session_update(self._session_id, update)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            loop.create_task(_send())

        def add_content_delta(self, content: str, phase_id: str) -> None:
            self._emit(update_agent_message_text(content))

        def add_chunk(self, chunk: Any, phase_id: str) -> None:
            delta = ""
            choices = getattr(chunk, "choices", None)
            if choices:
                ch0 = choices[0]
                d = getattr(ch0, "delta", None)
                if d is not None and getattr(d, "content", None):
                    delta = d.content or ""
            if delta:
                self._emit(update_agent_message_text(delta))

        def add_tool_call(self, phase_id: str, tool: Any) -> None:
            if "-action" in phase_id:
                iter_part = phase_id.split("-")[0]
                reasoning_id = f"{iter_part}-reasoning"
                try:
                    prog = self._tracker.progress(
                        reasoning_id,
                        status="completed",
                        content=[tool_content(text_block(""))],
                    )
                    self._emit(prog)
                except Exception:
                    pass

            title = getattr(tool, "tool_name", None) or tool.__class__.__name__
            kind = "think" if "reasoning" in phase_id else "other"
            start = self._tracker.start(phase_id, title=str(title), kind=kind, status="in_progress")
            self._emit(start)

        def add_tool_result(self, phase_id: str, content: str, tool_name: str | None = None) -> None:
            text = content if len(content) <= 8000 else content[:8000] + "\n…"
            prog = self._tracker.progress(
                phase_id,
                status="completed",
                content=[tool_content(text_block(text))],
            )
            self._emit(prog)

        def finish(self, phase_id: str, content: str | None = None, finish_reason: str = "stop") -> None:
            if content:
                self._emit(update_agent_message_text(str(content)))
            super().finish()

    return ACPStreamingGenerator
