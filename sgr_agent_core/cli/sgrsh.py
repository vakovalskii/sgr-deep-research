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
    """Read user input from buffer and decode as UTF-8 to avoid losing input on decode errors.

    Using input() can consume the line and then raise UnicodeDecodeError, so the next
    readline() would return the following (often empty) line. Always reading from
    stdin.buffer and decoding with errors='replace' ensures we never lose user input.
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.buffer.readline()
    return line.decode("utf-8", errors="replace").strip()


def find_config_file(config_file: str | None) -> Path | None:
    """Find config.yaml in current directory.

    Args:
        config_file: Optional explicit config file path

    Returns:
        Path to config file or None if not found
    """
    if config_file:
        path = Path(config_file)
        if path.exists():
            return path.resolve()
        return None

    # Look for config.yaml in current directory
    current_dir = Path.cwd()
    config_path = current_dir / "config.yaml"
    if config_path.exists():
        return config_path.resolve()

    return None


async def run_agent(agent: "BaseAgent") -> str | None:
    """Run agent and handle clarifications interactively.

    Args:
        agent: Agent instance to run

    Returns:
        Final result or None
    """
    # Start execution task
    execution_task = asyncio.create_task(agent.execute())

    try:
        # Monitor execution and handle clarifications
        while not execution_task.done():
            # Check if agent is waiting for clarification
            if agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                # Get message from last clarification/answer tool execution
                clarification_tool_names = (
                    "clarification_tool",
                    "clarificationtool",
                    "answer_tool",
                    "answertool",
                )
                message_to_show = None
                for log_entry in reversed(agent.log):
                    if log_entry.get("step_type") == "tool_execution":
                        tool_name = log_entry.get("tool_name")
                        if tool_name in clarification_tool_names:
                            message_to_show = log_entry.get("agent_tool_execution_result", "")
                            break

                if message_to_show:
                    print("\n" + message_to_show)
                    print()

                # Get user input
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

            # Small delay to avoid busy waiting
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
    """Interactive chat loop with agent.

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

    conversation_history = []

    try:
        while True:
            # Get user input
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

            # Add to conversation history
            conversation_history.append({"role": "user", "content": user_input})

            # Create agent with conversation history
            agent = await AgentFactory.create(agent_def, task_messages=conversation_history)

            # Run agent and handle clarifications
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
    config_path = find_config_file(args.config_file)
    if config_path is None:
        print("❌ Config file not found")
        if args.config_file:
            print(f"   Specified path: {args.config_file}")
        else:
            print("   Looking for: config.yaml in current directory")
        sys.exit(1)

    # Load configuration
    try:
        GlobalConfig.from_yaml(str(config_path))
        config = GlobalConfig()
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    # Get agent name
    agent_name = args.agent
    if agent_name is None:
        if not config.agents:
            print("❌ No agents found in config")
            sys.exit(1)
        agent_name = list(config.agents.keys())[0]
        if len(config.agents) > 1:
            print(f"ℹ️  Using first agent: {agent_name}")
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
