import os
from datetime import datetime
from functools import cache

from sgr_deep_research.core.models import SourceData
from sgr_deep_research.core.tools import BaseTool
from sgr_deep_research.settings import get_config

config = get_config()


class PromptLoader:
    @classmethod
    @cache
    def _load_prompt_file(cls, filename: str) -> str:
        user_file_path = os.path.join(config.prompts.prompts_dir, filename)
        lib_file_path = os.path.join(os.path.dirname(__file__), "..", config.prompts.prompts_dir, filename)

        for file_path in [user_file_path, lib_file_path]:
            if os.path.exists(file_path):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        return f.read().strip()
                except IOError as e:
                    raise IOError(f"Error reading prompt file {file_path}: {e}") from e

        raise FileNotFoundError(f"Prompt file not found: {user_file_path} or {lib_file_path}")

    @classmethod
    def get_system_prompt(cls, user_request: str, sources: list[SourceData], available_tools: list[BaseTool], previous_searches_summary: str = "") -> str:
        sources_formatted = "\n".join([str(source) for source in sources])
        template = cls._load_prompt_file(config.prompts.system_prompt_file)
        available_tools_str_list = [
            f"{i}. {tool.tool_name}: {tool.description}" for i, tool in enumerate(available_tools, start=1)
        ]
        try:
            # Prepare previous searches info
            previous_searches_info = ""
            if previous_searches_summary:
                previous_searches_info = f"\n\nPREVIOUS SEARCHES SUMMARY:\n{previous_searches_summary}"
            
            return template.format(
                current_date=datetime.now().strftime("%Y-%m-%d-%H:%M:%S"),
                available_tools="\n".join(available_tools_str_list),
                user_request=user_request,
                sources_formatted=sources_formatted,
                previous_searches_info=previous_searches_info,
            )
        except KeyError as e:
            raise KeyError(f"Missing placeholder in system prompt template: {e}") from e
