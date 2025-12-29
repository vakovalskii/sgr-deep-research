import logging
import sys
from pathlib import Path
from typing import ClassVar, Self

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from sgr_agent_core.agent_definition import AgentConfig, Definitions

logger = logging.getLogger(__name__)


class GlobalConfig(BaseSettings, AgentConfig, Definitions):
    _instance: ClassVar[Self | None] = None
    _initialized: ClassVar[bool] = False
    _config_path: ClassVar[Path | None] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        if self._initialized:
            return
        super().__init__(*args, **kwargs)
        self.__class__._initialized = True

    model_config = SettingsConfigDict(
        env_prefix="SGR__",
        extra="ignore",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> Self:
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
        cls._config_path = yaml_path.resolve()
        config_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        main_config_agents = config_data.pop("agents", {})
        if cls._instance is None:
            cls._instance = cls(
                **config_data,
            )
        else:
            cls._initialized = False
            cls._instance = cls(**config_data, agents=cls._instance.agents)
        # agents should be initialized last to allow merging
        cls._definitions_from_dict({"agents": main_config_agents}, config_path=cls._config_path)
        return cls._instance

    @classmethod
    def _resolve_relative_import(cls, base_class_path: str, config_path: Path | None) -> str:
        """Resolve relative import path to absolute module path for any package
        in sys.path."""
        if config_path is None:
            return base_class_path

        # Check if path is already absolute (first module part exists in sys.path)
        first_part = base_class_path.split(".")[0]
        for path in sys.path:
            if not path:
                continue
            try:
                path_obj = Path(path).resolve()
                if (path_obj / first_part).exists() or (path_obj / f"{first_part}.py").exists():
                    return base_class_path
            except (ValueError, AttributeError, OSError):
                continue

        # Relative path - find package root from config location
        try:
            config_dir = config_path.parent.resolve()
            package_root = None

            for path in sys.path:
                if not path:
                    continue
                try:
                    path_obj = Path(path).resolve()
                    if config_dir.is_relative_to(path_obj):
                        package_root = path_obj
                        break
                except (ValueError, AttributeError, OSError):
                    continue

            if package_root:
                module_base = str(config_dir.relative_to(package_root)).replace("/", ".").replace("\\", ".")
            else:
                module_base = config_dir.name

            class_path = base_class_path.lstrip(".") if base_class_path.startswith(".") else base_class_path
            return f"{module_base}.{class_path}" if module_base else class_path
        except (ValueError, AttributeError):
            return base_class_path

    @classmethod
    def _definitions_from_dict(cls, agents_data: dict, config_path: Path | None = None) -> Self:
        # Resolve relative imports in base_class before creating AgentDefinition
        for agent_name, agent_config in agents_data.get("agents", {}).items():
            agent_config["name"] = agent_name
            if "base_class" in agent_config and isinstance(agent_config["base_class"], str):
                agent_config["base_class"] = cls._resolve_relative_import(
                    agent_config["base_class"], config_path or cls._config_path
                )

        custom_agents = Definitions(**agents_data).agents

        # Get core agent class names that might be overridden
        from sgr_agent_core.services.registry import AgentRegistry

        core_agent_names = {name for name in AgentRegistry._items.keys()}

        # Check for agents that will be overridden
        overridden = set(cls._instance.agents.keys()) & set(custom_agents.keys())
        core_overridden = set(custom_agents.keys()) & core_agent_names

        if overridden:
            logger.info(f"Loaded agents will override existing agent definitions: {', '.join(sorted(overridden))}")

        if core_overridden:
            logger.info(
                f"Loaded agents will override core agent class names: {', '.join(sorted(core_overridden))}. "
                f"These definitions from config will be used instead of core class defaults."
            )

        # Explicitly replace agents with matching names (config agents take precedence)
        cls._instance.agents.update(custom_agents)
        return cls._instance

    @classmethod
    def definitions_from_yaml(cls, agents_yaml_path: str) -> Self:
        """Load agent definitions from YAML file and merge with existing
        agents.

        Args:
            agents_yaml_path: Path to YAML file with agent definitions

        Returns:
            GlobalConfig instance with merged agents

        Raises:
            FileNotFoundError: If YAML file not found
            ValueError: If YAML file doesn't contain 'agents' key
        """
        agents_yaml_path = Path(agents_yaml_path)
        if not agents_yaml_path.exists():
            raise FileNotFoundError(f"Agents definitions file not found: {agents_yaml_path}")

        yaml_data = yaml.safe_load(agents_yaml_path.read_text(encoding="utf-8"))
        if not yaml_data.get("agents"):
            raise ValueError(f"Agents definitions file must contain 'agents' key: {agents_yaml_path}")

        return cls._definitions_from_dict(yaml_data, config_path=agents_yaml_path.resolve())
