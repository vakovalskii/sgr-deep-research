import importlib.util
import inspect
import logging
import os
from functools import cached_property
from pathlib import Path
from typing import Any, Literal, Self, Union

import yaml
from fastmcp.mcp_config import MCPConfig
from pydantic import BaseModel, Field, FilePath, ImportString, computed_field, field_validator, model_validator

# Element of AgentDefinition.tools: name (str), class (type), or dict with "name" + kwargs
ToolItem = Union[str, type[Any], dict[str, Any]]
logger = logging.getLogger(__name__)


def validate_import_string_points_to_file(import_string: Any) -> Any:
    """Ensure ImportString based value points to an existing file.

    A dotted path indicates an import string (e.g., tools.ReadFileTool).
    We use importlib to automatically search for the module in sys.path.

    Args:
        import_string: The import string to validate

    Returns:
        The validated import string

    Raises:
        FileNotFoundError: If the module cannot be found in sys.path
    """
    if isinstance(import_string, str) and "." in import_string:
        module_parts = import_string.split(".")
        if len(module_parts) >= 2:
            # Get module path (everything except the class name)
            module_path = ".".join(module_parts[:-1])
            # Use importlib to find module in sys.path automatically
            try:
                spec = importlib.util.find_spec(module_path)
                if spec is None or spec.origin is None:
                    raise ModuleNotFoundError()
            except ModuleNotFoundError as e:
                # Convert ModuleNotFoundError to FileNotFoundError for consistency
                file_path = Path(*module_parts[:-1]).with_suffix(".py")
                raise FileNotFoundError(
                    f"base_class import '{import_string}' points to '{file_path}', "
                    f"but the file could not be found in sys.path"
                ) from e
    return import_string


class LLMConfig(BaseModel, extra="allow"):
    api_key: str | None = Field(default=None, description="API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="Base URL")
    model: str = Field(default="gpt-4o-mini", description="Model to use")
    max_tokens: int = Field(default=8000, description="Maximum number of output tokens")
    temperature: float = Field(default=0.4, ge=0.0, le=1.0, description="Generation temperature")
    proxy: str | None = Field(
        default=None, description="Proxy URL (e.g., socks5://127.0.0.1:1081 or http://127.0.0.1:8080)"
    )

    def to_openai_client_kwargs(self) -> dict[str, Any]:
        return self.model_dump(exclude={"api_key", "base_url", "proxy"})


class SearchConfig(BaseModel, extra="allow"):
    tavily_api_key: str | None = Field(default=None, description="Tavily API key")
    tavily_api_base_url: str = Field(default="https://api.tavily.com", description="Tavily API base URL")

    max_searches: int = Field(default=4, ge=0, description="Maximum number of searches")
    max_results: int = Field(default=10, ge=1, description="Maximum number of search results")
    content_limit: int = Field(default=3500, gt=0, description="Content character limit per source")


class PromptsConfig(BaseModel, extra="allow"):
    system_prompt_file: FilePath | None = Field(
        default=os.path.join(os.path.dirname(__file__), "prompts/system_prompt.txt"),
        description="Path to system prompt file",
    )
    initial_user_request_file: FilePath | None = Field(
        default=os.path.join(os.path.dirname(__file__), "prompts/initial_user_request.txt"),
        description="Path to initial user request file",
    )
    clarification_response_file: FilePath | None = Field(
        default=os.path.join(os.path.dirname(__file__), "prompts/clarification_response.txt"),
        description="Path to clarification response file",
    )
    system_prompt_str: str | None = None
    initial_user_request_str: str | None = None
    clarification_response_str: str | None = None

    @computed_field
    @cached_property
    def system_prompt(self) -> str:
        return self.system_prompt_str or self._load_prompt_file(self.system_prompt_file)

    @computed_field
    @cached_property
    def initial_user_request(self) -> str:
        return self.initial_user_request_str or self._load_prompt_file(self.initial_user_request_file)

    @computed_field
    @cached_property
    def clarification_response(self) -> str:
        return self.clarification_response_str or self._load_prompt_file(self.clarification_response_file)

    @staticmethod
    def _load_prompt_file(file_path: str | None) -> str | None:
        """Load prompt content from a file."""
        return Path(file_path).read_text(encoding="utf-8")

    @model_validator(mode="after")
    def defaults_validator(self):
        for attr, file_attr in zip(
            ["system_prompt_str", "initial_user_request_str", "clarification_response_str"],
            ["system_prompt_file", "initial_user_request_file", "clarification_response_file"],
        ):
            field = getattr(self, attr)
            file_field: FilePath = getattr(self, file_attr)
            if not field and not file_field:
                raise ValueError(f"{attr} or {file_attr} must be provided")
            if file_field:
                project_path = Path(file_field)
                if not project_path.exists():
                    raise FileNotFoundError(f"Prompt file '{project_path.absolute()}' not found")
        return self

    def __repr__(self) -> str:
        return (
            f"PromptsConfig(system_prompt='{self.system_prompt[:100]}...', "
            f"initial_user_request='{self.initial_user_request[:100]}...', "
            f"clarification_response='{self.clarification_response[:100]}...')"
        )


class ExecutionConfig(BaseModel, extra="allow"):
    """Execution parameters and limits for agents.

    You can add any additional fields as needed.
    """

    max_clarifications: int = Field(default=3, ge=0, description="Maximum number of clarifications")
    max_iterations: int = Field(default=10, gt=0, description="Maximum number of iterations")
    mcp_context_limit: int = Field(default=15000, gt=0, description="Maximum context length from MCP server response")

    streaming_generator: Literal["openai", "open_webui"] = Field(
        default="openai",
        description="Streaming generator for agent output format",
    )

    logs_dir: str | None = Field(
        default="logs", description="Directory for saving bot logs. Set to None or empty string to disable logging."
    )
    reports_dir: str = Field(default="reports", description="Directory for saving reports")


class AgentConfig(BaseModel, extra="allow"):
    """Agent configuration with all settings.

    The 'extra="allow"' allows additional fields for agent-specific
    parameters (e.g., working_directory for file agents).
    """

    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM settings")
    search: SearchConfig | None = Field(default=None, description="Search settings")
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig, description="Execution settings")
    prompts: PromptsConfig = Field(default_factory=PromptsConfig, description="Prompts settings")
    mcp: MCPConfig = Field(default_factory=MCPConfig, description="MCP settings")


class AgentDefinition(AgentConfig):
    """Definition of a custom agent.

    Agents can override global settings by providing:
    - llm: dict with keys matching LLMConfig (api_key, base_url, model, etc.)
    - prompts: dict with keys matching PromptsConfig (system_prompt_file, etc.)
    - ExecutionConfig: execution parameters and limits
    - tools: list of tool names to include
    """

    name: str = Field(description="Unique agent name/ID")
    # ToDo: not sure how to type this properly and avoid circular imports
    base_class: type[Any] | ImportString | str = Field(description="Agent class name")
    tools: list[ToolItem] = Field(
        default_factory=list,
        description="List of tool names, classes, or dicts with 'name' and optional kwargs for the tool",
    )

    @field_validator("tools", mode="before")
    @classmethod
    def tools_dict_must_have_name(cls, v: Any) -> Any:
        """Ensure each dict item in tools has a 'name' key."""
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, dict):
                if "name" not in item:
                    raise ValueError("Tool dict must have 'name' key")
                result.append(item)
            else:
                result.append(item)
        return result

    @field_validator("base_class", mode="before")
    def base_class_import_points_to_file(cls, v: Any) -> Any:
        """Ensure ImportString based base_class points to an existing file to
        catch a FileError and not interpret it as str class_name.

        A dotted path indicates an import string (e.g.,
        dir.agent.MyAgent). We use importlib to automatically search for
        the module in sys.path.
        """
        return validate_import_string_points_to_file(v)

    @model_validator(mode="before")
    def default_config_override_validator(cls, data):
        from sgr_agent_core.agent_config import GlobalConfig

        # check if already built model, otherwise build from config with JSON update
        if not isinstance(llm_conf := data.get("llm"), BaseModel):
            data["llm"] = GlobalConfig().llm.model_copy(update=llm_conf).model_dump()
        if not isinstance(search_conf := data.get("search"), BaseModel):
            data["search"] = (
                GlobalConfig().search.model_copy(update=search_conf).model_dump()
                if GlobalConfig().search
                else search_conf
            )
        if not isinstance(prompts_conf := data.get("prompts"), BaseModel):
            data["prompts"] = GlobalConfig().prompts.model_copy(update=prompts_conf).model_dump()
        if not isinstance(execution_conf := data.get("execution"), BaseModel):
            data["execution"] = GlobalConfig().execution.model_copy(update=execution_conf).model_dump()
        if not isinstance(mcp_conf := data.get("mcp"), BaseModel):
            data["mcp"] = GlobalConfig().mcp.model_copy(update=mcp_conf).model_dump(warnings=False)
        return data

    @model_validator(mode="after")
    def necessary_fields_validator(self) -> Self:
        if self.llm.api_key is None:
            raise ValueError(f"LLM API key is not provided for agent '{self.name}'")
        # Search API key can be provided via config.search or per-tool in tools array (kwargs)
        if not self.tools:
            raise ValueError(f"Tools are not provided for agent '{self.name}'")
        return self

    @field_validator("base_class", mode="after")
    def base_class_is_agent(cls, v: Any) -> type[Any]:
        from sgr_agent_core.base_agent import BaseAgent

        if inspect.isclass(v) and not issubclass(v, BaseAgent):
            raise TypeError("Imported base_class must be a subclass of BaseAgent")
        return v

    def __str__(self) -> str:
        base_class_name = self.base_class.__name__ if isinstance(self.base_class, type) else self.base_class
        tool_names = [
            t.get("name", t) if isinstance(t, dict) else (t.__name__ if isinstance(t, type) else t) for t in self.tools
        ]
        return (
            f"AgentDefinition(name='{self.name}', "
            f"base_class={base_class_name}, "
            f"tools={tool_names}, "
            f"execution={self.execution}), "
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> Self:
        try:
            return cls(**yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")))
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Agent definition file not found: {yaml_path}") from e


class ToolDefinition(BaseModel, extra="allow"):
    """Definition of a custom tool.

    Tools can be defined with:
    - base_class: Import string or class name (optional, defaults to sgr_agent_core.tools.{ToolName})
    - Any additional parameters for the tool (passed as kwargs at runtime; e.g. max_results, max_searches)
    """

    name: str = Field(description="Unique tool name/ID")
    base_class: Union[type[Any], ImportString, str, None] = Field(
        default=None, description="Tool class name (optional, defaults to sgr_agent_core.tools.{name})"
    )

    def tool_kwargs(self) -> dict[str, Any]:
        """Return extra fields as kwargs for the tool (global tool config)."""
        return {k: v for k, v in self.model_dump().items() if k not in ("name", "base_class")}

    @field_validator("base_class", mode="before")
    def base_class_import_points_to_file(cls, v: Any) -> Any:
        """Ensure ImportString based base_class points to an existing file.

        A dotted path indicates an import string (e.g.,
        tools.ReadFileTool). We use importlib to automatically search
        for the module in sys.path.
        """
        return validate_import_string_points_to_file(v)

    @field_validator("base_class", mode="after")
    def base_class_is_tool(cls, v: Any) -> Union[type[Any], None]:
        # Don't validate at definition time - validation happens when tool is actually used
        # This allows relative imports to work correctly
        if v is None:
            return None
        # Only validate if it's already a class
        if inspect.isclass(v):
            from sgr_agent_core.base_tool import BaseTool

            if not issubclass(v, BaseTool):
                raise TypeError("Imported base_class must be a subclass of BaseTool")
        return v

    def __str__(self) -> str:
        base_class_name = self.base_class.__name__ if isinstance(self.base_class, type) else self.base_class
        return f"ToolDefinition(name='{self.name}', base_class={base_class_name})"


class Definitions(BaseModel):
    agents: dict[str, AgentDefinition] = Field(
        default_factory=dict, description="Dictionary of agent definitions by name"
    )
    tools: dict[str, ToolDefinition] = Field(default_factory=dict, description="Dictionary of tool definitions by name")
