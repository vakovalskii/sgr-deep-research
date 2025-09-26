import asyncio
import json
import time

from openai.types.chat import ChatCompletionChunk


class StreamingGenerator:
    def __init__(self):
        self.queue = asyncio.Queue()

    def add(self, data: str):
        self.queue.put_nowait(data)

    def finish(self):
        self.queue.put_nowait(None)  # Завершающий сигнал

    async def stream(self):
        while True:
            data = await self.queue.get()
            if data is None:  # Завершающий символ
                break
            yield data


class OpenAIStreamingGenerator(StreamingGenerator):
    def __init__(self, model="gpt-4o"):
        super().__init__()
        self.model = model
        self.fingerprint = f"fp_{hex(hash(model))[-8:]}"
        self.id = f"chatcmpl-{int(time.time())}{hash(str(time.time()))}"[:29]
        self.created = int(time.time())
        self.choice_index = 0

    def add_chunk(self, chunk: ChatCompletionChunk):
        chunk.model = self.model
        # Convert to dict first, then use json.dumps with ensure_ascii=False
        chunk_dict = chunk.model_dump()
        super().add(f"data: {json.dumps(chunk_dict, ensure_ascii=False)}\n\n")

    def add_chunk_from_str(self, content: str):
        response = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": self.fingerprint,
            "choices": [
                {
                    "delta": {"content": content, "role": "assistant", "tool_calls": None},
                    "index": self.choice_index,
                    "finish_reason": None,
                    "logprobs": None,
                }
            ],
            "usage": None,
        }
        super().add(f"data: {json.dumps(response, ensure_ascii=False)}\n\n")

    def add_tool_call(self, tool_call_id: str, function_name: str, arguments: str):
        """Добавляет tool call chunk."""
        response = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": f"fp_{hex(hash(self.model))[-8:]}",
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": tool_call_id,
                                "type": "function",
                                "function": {"name": function_name, "arguments": arguments},
                            }
                        ]
                    },
                    "index": self.choice_index,
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
            "usage": None,
        }
        super().add(f"data: {json.dumps(response, ensure_ascii=False)}\n\n")

    def finish(self, finish_reason: str = "stop"):
        """Завершает stream с финальным chunk и usage."""
        final_response = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": f"fp_{hex(hash(self.model))[-8:]}",
            "choices": [{"index": self.choice_index, "delta": {}, "logprobs": None, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        super().add(f"data: {json.dumps(final_response, ensure_ascii=False)}\n\n")
        super().add("data: [DONE]\n\n")
        super().finish()
