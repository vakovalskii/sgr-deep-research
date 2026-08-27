"""CLI entrypoint: ``sgracp --config /path/to/config.yaml`` (ACP over stdio)."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys

from sgr_agent_core._optional import MissingDependencyError, require
from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.server.__main__ import load_config

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


def _run() -> None:
    """Load YAML config and run an ACP agent on stdio.

    ``agent-client-protocol`` ships in the ``[acp]`` extra, so it and the
    bridge that builds on it are imported here rather than at module scope.
    """
    run_agent = require("acp", feature="The 'sgracp' ACP stdio server").run_agent

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

    from sgr_agent_core.acp.bridge import SGRACPBridge

    bridge = SGRACPBridge(default_agent_name=default_name)
    asyncio.run(run_agent(bridge))


def main() -> None:
    """Console entrypoint for ``sgracp``.

    Reports a missing ``[acp]`` extra as a plain message instead of a
    traceback.
    """
    try:
        _run()
    except MissingDependencyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
