#!/usr/bin/env python3
"""
Quick launcher for SGR Agent CLI
"""

import subprocess
import sys
import os

def main():
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cli_path = os.path.join(script_dir, "cli_client.py")
    
    # Run the CLI client
    try:
        subprocess.run([sys.executable, cli_path], check=True)
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
    except FileNotFoundError:
        print("Error: cli_client.py not found!")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
