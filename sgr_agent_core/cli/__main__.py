"""Main entry point for sgrsh CLI command."""

import asyncio

from sgr_agent_core.cli.sgrsh import main as async_main


def main():
    """Synchronous entry point for sgrsh command."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
