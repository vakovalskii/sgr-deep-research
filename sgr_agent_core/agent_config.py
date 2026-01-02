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
        sys.path.append(str(yaml_path.resolve().parent))
        if not yaml_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
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
        cls._definitions_from_dict({"agents": main_config_agents})
        return cls._instance

    @classmethod
    def _definitions_from_dict(cls, agents_data: dict) -> Self:
        for agent_name, agent_config in agents_data.get("agents", {}).items():
            agent_config["name"] = agent_name

        custom_agents = Definitions(**agents_data).agents

        # Check for agents that will be overridden
        overridden = set(cls._instance.agents.keys()) & set(custom_agents.keys())
        if overridden:
            logger.warning(f"Loaded agents will override existing agents: " f"{', '.join(sorted(overridden))}")

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

        sys.path.append(str(agents_yaml_path.resolve().parent))
        if not agents_yaml_path.exists():
            raise FileNotFoundError(f"Agents definitions file not found: {agents_yaml_path}")

        yaml_data = yaml.safe_load(agents_yaml_path.read_text(encoding="utf-8"))
        if not yaml_data.get("agents"):
            raise ValueError(f"Agents definitions file must contain 'agents' key: {agents_yaml_path}")

        return cls._definitions_from_dict(yaml_data)
