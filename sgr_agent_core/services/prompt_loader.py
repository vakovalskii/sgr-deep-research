from datetime import datetime
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletionMessageParam

from sgr_agent_core.skills.rendering import render_available_skills

if TYPE_CHECKING:
    from sgr_agent_core import BaseTool, PromptsConfig
    from sgr_agent_core.skills import Skill


class PromptLoader:
    @classmethod
    def get_system_prompt(
        cls,
        available_tools: list[type["BaseTool"]],
        prompts_config: "PromptsConfig",
        available_skills: "list[Skill] | None" = None,
        max_skill_desc_chars: int = 500,
    ) -> str:
        template = prompts_config.system_prompt
        available_tools_str_list = [
            f"{i}. {tool.tool_name}: {tool.description}" for i, tool in enumerate(available_tools, start=1)
        ]
        skills_block = render_available_skills(available_skills or [], max_desc_chars=max_skill_desc_chars)

        try:
            rendered = template.format(
                available_tools="\n".join(available_tools_str_list),
                available_skills=skills_block,
            )
        except KeyError as e:
            raise KeyError(f"Missing placeholder in system prompt template: {e}") from e

        # If a custom template omits {available_skills}, append the catalog so the
        # agent still sees skills it can invoke via use_skill (autonomous discovery).
        if skills_block and "{available_skills}" not in template:
            rendered = f"{rendered}\n\n{skills_block}"
        return rendered

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
