"""CLI entrypoint: ``sgracp --config /path/to/config.yaml`` (ACP over stdio)."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys

from acp import run_agent

from sgr_agent_core.acp.bridge import SGRACPBridge
from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.server.__main__ import load_config
from sgr_agent_core.services import build_checkpoint_store

logger = logging.getLogger(__name__)


def _preload_agent_modules_from_config() -> None:
    """Import agent modules so ImportString classes register in
    AgentRegistry."""
    cfg = GlobalConfig()
    if cfg.config_dir:
        root = cfg.config_dir.resolve()
        # Insert parent first so `import sgr_file_agent` resolves to the package
        # (example dir contains both package `sgr_file_agent/` and `sgr_file_agent.py`).
        parent = str(root.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        root_s = str(root)
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
    for ad in cfg.agents.values():
        bc = ad.base_class
        if isinstance(bc, str) and "." in bc:
            mod_name = bc.rsplit(".", 1)[0]
            try:
                importlib.import_module(mod_name)
            except ModuleNotFoundError:
                logger.warning("Could not import agent module %s for %s", mod_name, ad.name)


def main() -> None:
    """Load YAML config and run an ACP agent on stdio."""
    parser = argparse.ArgumentParser(prog="sgracp", description="SGR Agent Core (Agent Client Protocol, stdio)")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to config.yaml (same format as the sgr HTTP server)",
    )
    parser.add_argument(
        "--agents",
        default=None,
        help="Optional path to agents-only YAML (merged into definitions)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

    load_config(args.config, args.agents)
    _preload_agent_modules_from_config()
    cfg = GlobalConfig()
    default_name = cfg.acp.agent if cfg.acp else None
    checkpoint_store = build_checkpoint_store(cfg.execution.checkpoint)
    bridge = SGRACPBridge(default_agent_name=default_name, checkpoint_store=checkpoint_store)
    asyncio.run(run_agent(bridge))


if __name__ == "__main__":
    main()
