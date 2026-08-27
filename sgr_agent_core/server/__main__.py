"""Main entry point for SGR Agent Core API server."""

import logging
import sys
from pathlib import Path

import yaml

from sgr_agent_core._optional import MissingDependencyError, require
from sgr_agent_core.agent_config import GlobalConfig

logger = logging.getLogger(__name__)


def load_config(config_file: str, agents_file: str | None = None) -> GlobalConfig:
    """Load configuration and agents from YAML files.

    This function implements the configuration loading logic:
    1. Load config.yaml (including agents section if present)
    2. Load agents.yaml if provided (overrides existing agents)

    Agents are loaded dynamically from the paths specified in base_class fields.
    The core has no hard dependencies on specific agent implementations.

    Args:
        config_file: Path to config.yaml file
        agents_file: Optional path to agents.yaml file

    Returns:
        GlobalConfig instance with loaded configuration and agents
    """
    config = GlobalConfig.from_yaml(config_file)

    # Load agents from separate file if exists (overrides config.yaml agents)
    if agents_file and Path(agents_file).exists():
        try:
            config.definitions_from_yaml(agents_file)
        except ValueError as e:
            logger.error(f"Invalid agents file format '{agents_file}': {e}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in agents file '{agents_file}': {e}")
            raise

    return config


def _run() -> None:
    """Start FastAPI server.

    Config from ServerConfig (env + CLI, see settings.py).

    fastapi and uvicorn ship in the ``[server]`` extra, so they are imported
    here rather than at module scope: importing this module (``load_config`` is
    reused by the ACP entrypoint) must not require the server extra.
    """
    uvicorn = require("uvicorn", feature="The 'sgr' HTTP server")
    require("fastapi", feature="The 'sgr' HTTP server")

    from sgr_agent_core.server.app import app
    from sgr_agent_core.server.settings import ServerConfig, setup_logging

    server_config = ServerConfig()
    setup_logging(server_config.logging_file)
    load_config(server_config.config_file, server_config.agents_file)
    uvicorn.run(app, host=server_config.host, port=server_config.port, log_level="info")


def main():
    """Console entrypoint for ``sgr``.

    Reports a missing ``[server]`` extra as a plain message instead of a
    traceback.
    """
    try:
        _run()
    except MissingDependencyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
