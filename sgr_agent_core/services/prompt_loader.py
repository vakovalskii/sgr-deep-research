from datetime import datetime
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletionMessageParam

if TYPE_CHECKING:
    from sgr_agent_core import BaseTool, PromptsConfig


class PromptLoader:
    @classmethod
    def get_system_prompt(cls, available_tools: list[type["BaseTool"]], prompts_config: "PromptsConfig") -> str:
        template = prompts_config.system_prompt
        available_tools_str_list = [
            f"{i}. {tool.tool_name}: {tool.description}" for i, tool in enumerate(available_tools, start=1)
        ]

        try:
            return template.format(
                available_tools="\n".join(available_tools_str_list),
            )
        except KeyError as e:
            raise KeyError(f"Missing placeholder in system prompt template: {e}") from e

    @classmethod
    def get_initial_user_request(
        cls,
        messages: list[ChatCompletionMessageParam],
        prompts_config: "PromptsConfig",
        current_datetime=datetime.now(),
    ) -> str:
        template = prompts_config.initial_user_request
        try:
            return template.format(current_date=current_datetime.strftime("%Y-%m-%d %H:%M:%S"))
        except KeyError as e:
            raise KeyError(f"Missing placeholder in system prompt template: {e}") from e

    @classmethod
    def get_clarification_template(
        cls,
        messages: list[ChatCompletionMessageParam],
        prompts_config: "PromptsConfig",
        current_datetime=datetime.now(),
    ) -> str:
        template = prompts_config.clarification_response
        try:
            return template.format(current_date=current_datetime.strftime("%Y-%m-%d %H:%M:%S"))
        except KeyError as e:
            raise KeyError(f"Missing placeholder in system prompt template: {e}") from e
