#!/usr/bin/env python3
"""SGR Shell - Interactive CLI for SGR agents.

Usage:
    sgrsh "Your query here"
    sgrsh --agent sgr_agent "Your query here"
    sgrsh --config-file config.yaml --agent sgr_agent
    sgrsh -c config.yaml -a sgr_agent
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.models import AgentStatesEnum

if TYPE_CHECKING:
    from sgr_agent_core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


def _read_user_input(prompt: str) -> str:
    """Read user input from buffer and decode as UTF-8 to avoid losing input on
    decode errors.

    Using input() can consume the line and then raise
    UnicodeDecodeError, so the next readline() would return the
    following (often empty) line. Always reading from stdin.buffer and
    decoding with errors='replace' ensures we never lose user input.
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.buffer.readline()
    return line.decode("utf-8", errors="replace").strip()


def find_config_file(config_file: str | None) -> Path:
    """Find config.yaml in current directory.

    Args:
        config_file: Optional explicit config file path

    Returns:
        Path to config file or None if not found
    """
    path = Path(config_file) if config_file else Path.cwd() / "config.yaml"
    if path.exists():
        return path.resolve()
    raise FileNotFoundError("Config file not found")


async def run_agent(agent: "BaseAgent") -> str | None:
    """Run one agent to completion; handle clarification prompts while it runs.

    One agent = one turn. This function does not create or switch agents.
    It only waits for the given agent to finish, and when the agent calls
    ClarificationTool/AnswerTool, reads user input and feeds it back.

    Args:
        agent: Agent instance to run (single turn)

    Returns:
        Final result or None
    """
    execution_task = asyncio.create_task(agent.execute())

    try:
        # Wait for this agent to finish; only react when it asks for clarification
        while not execution_task.done():
            if agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                if agent._context.execution_result:
                    print("\n" + agent._context.execution_result)
                    print()

                try:
                    user_input = _read_user_input("You: ")
                except (KeyboardInterrupt, EOFError):
                    # User pressed Ctrl+C or EOF during input
                    print("\n\n⚠️  Interrupted by user")
                    await agent.cancel()
                    return None

                if user_input:
                    await agent.provide_clarification([{"role": "user", "content": user_input}])
                else:
                    # Empty input - cancel execution
                    await agent.cancel()
                    return None

            await asyncio.sleep(0.1)

        # Get final result
        try:
            result = await execution_task
            return result
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return None
    except KeyboardInterrupt:
        # User pressed Ctrl+C during execution
        print("\n\n⚠️  Interrupted by user")
        await agent.cancel()
        return None


async def chat_loop(agent_def_name: str, config: GlobalConfig):
    """Interactive session: one short-lived agent per user message, shared history.

    Model: 1 agent = 1 turn. Each user message creates a new agent with
    conversation_history; that agent runs to completion and exits. The result
    is appended to history; next message gets a fresh agent with full context.
    No agent reuse or switching mid-session.

    Args:
        agent_def_name: Name of agent definition
        config: GlobalConfig instance
    """
    agent_def = config.agents.get(agent_def_name)
    if agent_def is None:
        print(f"❌ Agent '{agent_def_name}' not found in config")
        print(f"Available agents: {', '.join(config.agents.keys())}")
        sys.exit(1)

    print(f"✅ Using agent: {agent_def_name}")
    print("Type 'quit' or 'exit' to end the session (or press Ctrl+C)\n")

    conversation_history: list[dict] = []

    try:
        while True:
            try:
                user_input = _read_user_input("You: ")
            except (KeyboardInterrupt, EOFError):
                # User pressed Ctrl+C or EOF during input
                print("\n\n👋 Goodbye!")
                break

            if user_input.lower() in ("quit", "exit", "q"):
                break

            if not user_input:
                continue

            conversation_history.append({"role": "user", "content": user_input})
            agent = await AgentFactory.create(agent_def, task_messages=conversation_history)
            result = await run_agent(agent)

            if result:
                print(f"\nAgent: {result}\n")
                sys.stdout.flush()
                # Add agent response to history
                conversation_history.append({"role": "assistant", "content": result})
            else:
                print("\nAgent: No response received\n")
                sys.stdout.flush()
    except KeyboardInterrupt:
        # User pressed Ctrl+C during agent execution
        print("\n\n👋 Goodbye!")


async def main():
    """Main entry point for sgrsh command."""
    parser = argparse.ArgumentParser(
        description="SGR Shell - Interactive CLI for SGR agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sgrsh "Найди цену биткоина"
  sgrsh --agent sgr_agent "What is AI?"
  sgrsh -c config.yaml -a sgr_agent
        """,
    )
    parser.add_argument(
        "-c",
        "--config-file",
        type=str,
        default=None,
        help="Path to config.yaml file (default: looks for config.yaml in current directory)",
    )
    parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help="Agent name to use (default: first agent in config)",
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Initial query (optional - if not provided, starts interactive chat)",
    )

    args = parser.parse_args()

    # Setup minimal logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
    )

    # Find config file
    try:
        config_path = find_config_file(args.config_file)
    except FileNotFoundError:
        print("❌ Config file not found")
        if args.config_file:
            print(f"   Specified path: {args.config_file}")
        else:
            print("   Looking for: config.yaml in current directory")
        sys.exit(1)

    # Load configuration
    try:
        config = GlobalConfig.from_yaml(str(config_path))
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    # Get agent name (default: dialog_agent if present, else first in config)
    agent_name = args.agent
    if agent_name is None:
        if not config.agents:
            print("❌ No agents found in config")
            sys.exit(1)
        agent_name = "dialog_agent" if "dialog_agent" in config.agents else list(config.agents.keys())[0]
        if len(config.agents) > 1:
            print(f"ℹ️  Using agent: {agent_name}")
            print(f"   Available agents: {', '.join(config.agents.keys())}")

    # Check if query provided
    query = " ".join(args.query) if args.query else None

    if query:
        # Single query mode
        agent_def = config.agents.get(agent_name)
        if agent_def is None:
            print(f"❌ Agent '{agent_name}' not found in config")
            print(f"Available agents: {', '.join(config.agents.keys())}")
            sys.exit(1)

        # Create agent
        task_messages = [{"role": "user", "content": query}]
        agent = await AgentFactory.create(agent_def, task_messages)

        # Run agent
        result = await run_agent(agent)

        if result:
            print(f"\n{result}")
        else:
            print("\nNo response received")
    else:
        # Interactive chat mode
        await chat_loop(agent_name, config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # User pressed Ctrl+C - exit gracefully
        print("\n\n👋 Goodbye!")
        sys.exit(0)
