"""Open-WebUI specific streaming generator with HTML details tag support."""

import html
import json

from sgr_agent_core.stream import OpenAIStreamingGenerator


class OpenWebUIStreamingGenerator(OpenAIStreamingGenerator):
    """Extended streaming generator with Open-WebUI specific HTML details tag support."""

    def add_tool_call_start(self, tool_call_id: str, function_name: str, arguments: str):
        """
        Показываем начало выполнения инструмента с shimmer анимацией.
        
        Args:
            tool_call_id: Уникальный ID вызова инструмента для связи с результатом
            function_name: Название функции инструмента для отображения
            arguments: JSON аргументы инструмента для отладки
        """
        # Отправляем details блок с done="false" для shimmer эффекта
        # ВАЖНО: OpenWebUI требует перевод строки после <details> тега
        tool_html = (
            f'<details type="tool_calls" done="false" id="{tool_call_id}" '
            f'name="{function_name}" '
            f'arguments="{html.escape(arguments)}">\n'
            f'<summary>Executing {function_name}...</summary>\n'
            f'</details>\n'
        )
        
        response = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": self.fingerprint,
            "choices": [
                {
                    "delta": {"content": tool_html, "role": "assistant"},
                    "index": self.choice_index,
                    "finish_reason": None,
                    "logprobs": None,
                }
            ],
            "usage": None,
        }
        super().add(f"data: {json.dumps(response)}\n\n")
    
    def add_tool_call_with_result(self, tool_call_id: str, function_name: str, arguments: str, result: str, reasoning: str = ""):
        """
        Добавляем завершённый вызов инструмента с результатом.
        
        Args:
            tool_call_id: Уникальный ID вызова инструмента для связи с началом
            function_name: Название функции инструмента для отображения
            arguments: JSON аргументы инструмента для отладки
            result: Результат выполнения инструмента для отображения
            reasoning: Описание reasoning для отображения в details (опционально)
        """
        # Отправляем завершённый блок с done="true" и результатом
        # Если есть reasoning, показываем его в summary, иначе стандартный текст
        summary_text = reasoning if reasoning else f"View Result from {function_name}"
        tool_html = (
            f'<details type="tool_calls" done="true" id="{tool_call_id}-result" '
            f'name="{function_name}" '
            f'arguments="{html.escape(arguments)}" '
            f'result="{html.escape(json.dumps(result, ensure_ascii=False))}">\n'
            f'<summary>{html.escape(summary_text)}</summary>\n'
            f'</details>\n\n'
        )
        
        response = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": self.fingerprint,
            "choices": [
                {
                    "delta": {"content": tool_html, "role": "assistant"},
                    "index": self.choice_index,
                    "finish_reason": None,
                    "logprobs": None,
                }
            ],
            "usage": None,
        }
        super().add(f"data: {json.dumps(response)}\n\n")




