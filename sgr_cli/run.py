#!/usr/bin/env python
"""Entry point for running SGR CLI directly from sgr-cli directory."""

import sys
from pathlib import Path

# Add parent directory to Python path to allow imports
current_dir = Path(__file__).parent.resolve()
parent_dir = current_dir.parent.resolve()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Now import and run
from sgr_cli.app.app import main

if __name__ == "__main__":
    main()
