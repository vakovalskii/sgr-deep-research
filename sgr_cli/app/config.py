"""Configuration management for SGR CLI."""

import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from sgr_agent_core.agent_config import GlobalConfig

logger = logging.getLogger(__name__)


class CLIConfig(BaseModel):
    """CLI-specific configuration."""

    theme: str = Field(default="default", description="UI theme name")
    show_tools_panel: bool = Field(default=False, description="Show tools panel by default (use Ctrl+T to toggle)")
    show_history_panel: bool = Field(default=False, description="Show history panel by default (use Ctrl+H to toggle)")
    tools_panel_width: int = Field(default=40, description="Tools panel width")
    history_panel_height: int = Field(default=10, description="History panel height")
    auto_approve_tools: bool = Field(default=False, description="Auto-approve tool execution")
    max_history_items: int = Field(default=100, description="Maximum history items to keep")


def load_cli_config(config_path: Optional[Path] = None) -> CLIConfig:
    """Load CLI configuration from YAML file.

    Args:
        config_path: Path to CLI config file. If None, looks for cli.yaml in current directory.

    Returns:
        CLIConfig instance
    """
    if config_path is None:
        config_path = Path("cli.yaml")

    if not config_path.exists():
        logger.info(f"CLI config file not found at {config_path}, using defaults")
        return CLIConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        return CLIConfig(**config_data)
    except Exception as e:
        logger.warning(f"Failed to load CLI config from {config_path}: {e}, using defaults")
        return CLIConfig()


def load_agent_config(
    config_path: Path,
    agents_path: Optional[Path] = None,
) -> GlobalConfig:
    """Load agent configuration from YAML file(s).

    Args:
        config_path: Path to main config YAML file (config.yaml)
        agents_path: Optional path to agents YAML file (agents.yaml).
                    If provided, agents will be loaded from this file and merged.

    Returns:
        GlobalConfig instance with loaded configuration

    Examples:
        # Load from single config file
        config = load_agent_config(Path("config.yaml"))

        # Load from config.yaml + agents.yaml
        config = load_agent_config(Path("config.yaml"), Path("agents.yaml"))
    """
    # Load main config
    config = GlobalConfig.from_yaml(str(config_path))

    # Load agents from separate file if provided
    if agents_path:
        if not agents_path.exists():
            logger.warning(f"Agents file not found: {agents_path}, using agents from config.yaml")
        else:
            try:
                config.definitions_from_yaml(str(agents_path))
                logger.info(f"Loaded agents from {agents_path}")
            except Exception as e:
                logger.warning(f"Failed to load agents from {agents_path}: {e}")

    return config
