import logging
import logging.config
import os
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ServerConfig(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True, cli_kebab_case=True)
    logging_file: str = Field(default="logging_config.yaml", description="Logging configuration file path")
    config_file: str = Field(default="config.yaml", description="sgr core configuration file path")
    agents_file: str | None = Field(default=None, description="Optional agents definitions file path")
    host: str = Field(default="0.0.0.0", description="Host to listen on")
    port: int = Field(default=8010, gt=0, le=65535, description="Port to listen on")


def setup_logging(logging_file: str) -> None:
    """Setup logging configuration from YAML file.

    Args:
        logging_file: Path to logging configuration file.
    """
    logging_config_path = Path(logging_file)
    if not logging_config_path.exists():
        logger.warning(f"Logging config file not found: {logging_config_path}")
        return

    with open(logging_config_path, "r", encoding="utf-8") as f:
        logging_config = yaml.safe_load(f)
        os.makedirs("logs", exist_ok=True)

    logging.config.dictConfig(logging_config)
