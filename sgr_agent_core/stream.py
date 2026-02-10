import asyncio
import json
import time
from typing import Any, AsyncGenerator

from openai.types.chat import ChatCompletionChunk

from sgr_agent_core.base_tool import BaseTool
from sgr_agent_core.services.registry import StreamingGeneratorRegistry


class StreamingGeneratorRegistryMixin:
    """Mixin that registers streaming generator subclasses in
    StreamingGeneratorRegistry."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ != "BaseStreamingGenerator":
            StreamingGeneratorRegistry.register(cls, name=cls.name)


class BaseStreamingGenerator(StreamingGeneratorRegistryMixin):
    """Base class for streaming generators.

    Subclasses are auto-registered by name.
    """

    name: str = "base_streaming_generator"

    def __init__(self):
        self.queue = asyncio.Queue()

    def add(self, data: str):
        self.queue.put_nowait(data)

    def add_done(self):
        """Adds [DONE] marker without finishing the stream."""
        self.queue.put_nowait("data: [DONE]\n\n")

    def finish(self):
        self.queue.put_nowait(None)  # Termination signal

    async def stream(self):
        while True:
            data = await self.queue.get()
            if data is None:  # Termination signal
                break
            yield data


class OpenAIStreamingGenerator(BaseStreamingGenerator):
    """OpenAI SSE format.

    Registered as 'openai'.
    """

    name: str = "openai"

    def __init__(self, agent_id: str):
        super().__init__()
        self.agent_id = agent_id
        self.choice_index = 0

    def _create_base_chunk(self, phase_id: str) -> dict:
        """Creates base structure for a chunk."""
        return {
            "id": phase_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.agent_id,
            "system_fingerprint": None,
            "choices": [],
            "usage": None,
        }

    def add_chunk(self, chunk: ChatCompletionChunk, phase_id: str):
        """Adds a ready-made ChatCompletionChunk from OpenAI client."""
        chunk.id = phase_id
        chunk.model = self.agent_id
        chunk.created = int(time.time())
        super().add(f"data: {chunk.model_dump_json()}\n\n")

    def add_tool_call(self, phase_id: str, tool: BaseTool) -> None:
        """No-op: we already stream tool by chunks"""
        pass

    def add_content_delta(self, content: str, phase_id: str):
        """Adds a chunk with content delta."""
        response = self._create_base_chunk(phase_id)
        response["choices"] = [
            {
                "delta": {"content": content, "role": "assistant", "tool_calls": None},
                "index": self.choice_index,
                "finish_reason": None,
                "logprobs": None,
            }
        ]
        super().add(f"data: {json.dumps(response)}\n\n")

    def add_tool_result(self, phase_id: str, content: str, tool_name: str | None = None):
        """Adds a tool result as a streaming chunk (chat.completion.chunk with
        delta).

        Uses delta like other stream chunks; this is not the full
        chat.completion format from the retrieve endpoint (which has
        choices[].message).
        """
        response = self._create_base_chunk(phase_id)
        response["choices"] = [
            {
                "delta": {
                    "role": "tool",
                    "content": content,
                    "tool_call_id": phase_id,
                },
                "index": self.choice_index,
                "logprobs": None,
                "finish_reason": None,
            }
        ]
        super().add(f"data: {json.dumps(response)}\n\n")

    def finish(self, phase_id: str, content: str | None = None, finish_reason: str = "stop"):
        """Finishes content stream with the final chunk."""
        response = self._create_base_chunk(phase_id)
        response["choices"] = [
            {
                "index": self.choice_index,
                "delta": {"content": content, "role": "assistant"} if content else None,
                "logprobs": None,
                "finish_reason": finish_reason,
            }
        ]
        response["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        super().add(f"data: {json.dumps(response)}\n\n")
        super().add("data: [DONE]\n\n")
        super().finish()

    async def wrap_tool_stream(self, original_stream, phase_id: str) -> AsyncGenerator[Any, None]:
        """Restream and fill with agent metainfo."""
        async for event in original_stream:
            yield event
            self.add_chunk(event.chunk, phase_id)


class OpenWebUIStreamingGenerator(OpenAIStreamingGenerator):
    """Streaming generator: tool calls and results in <details>. Registered as 'open_webui'."""

    name: str = "open_webui"

    def __init__(self, agent_id: str):
        super().__init__(agent_id)

    def add_chunk(self, chunk: ChatCompletionChunk, phase_id: str) -> None:
        """No-op: we group and send only final tool/reasoning in <details>, not raw chunks."""
        pass

    def _wrap_in_code_block(self, content: str, language: str = "") -> str:
        """Wraps content in a Markdown code block."""
        if not content:  # otherwise confusing placeholder will show
            return "{}"
        lang_suffix = f" {language}" if language else ""
        return f"```{lang_suffix}\n{content}\n```"

    def add_tool_call(self, phase_id: str, tool: BaseTool) -> None:
        """Formats tool/reasoning and sends in <details>."""
        block = (
            f"<details>\n"
            f"<summary>Phase: {phase_id} Tool Call: {tool.tool_name}</summary>\n\n"
            f"{self._wrap_in_code_block(tool.model_dump_json(indent=2), language='json')}\n\n</details>\n\n"
        )
        self.add_content_delta(block, phase_id)

    def add_tool_result(self, phase_id: str, content: str, tool_name: str | None = None):
        """Adds tool result in collapsible Markdown (collapsed by default)."""
        tool_display_name = tool_name or "Tool"
        result_header = f"<summary>Phase: {phase_id} Tool Result: {tool_display_name}</summary>\n\n"
        try:
            json.loads(content)
            wrapped_content = self._wrap_in_code_block(content, "json")
        except (json.JSONDecodeError, ValueError):
            wrapped_content = self._wrap_in_code_block(content)
        result_content = f"<details>\n{result_header}{wrapped_content}\n\n</details>\n\n"
        self.add_content_delta(result_content, phase_id)
