"""Expose skills as MCP prompts.

MCP ``prompts`` are the user-controlled primitive that clients (Claude Code,
Zed, ...) render as slash commands. Building a FastMCP server whose prompts are
the project's skills makes skills "visible as commands" over MCP: ``prompts/list``
advertises name + description, and ``prompts/get`` returns the skill body.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from fastmcp import FastMCP
from fastmcp.prompts import Prompt

from sgr_agent_core.skills.models import Skill

DEFAULT_SERVER_NAME = "sgr-skills"


def _make_prompt_fn(skill: Skill) -> Callable[..., str]:
    """Build the prompt callable that returns a skill's body (+ optional args)."""

    def prompt_fn(arguments: str = "") -> str:
        body = skill.body.strip() or "(this skill has no additional instructions)"
        arguments = (arguments or "").strip()
        return f"{body}\n\n{arguments}".strip() if arguments else body

    prompt_fn.__doc__ = skill.description
    return prompt_fn


def build_skills_mcp_server(skills: Iterable[Skill], name: str = DEFAULT_SERVER_NAME) -> FastMCP:
    """Build a FastMCP server exposing user-invocable skills as prompts.

    Args:
        skills: Skills to expose.
        name: MCP server name.

    Returns:
        A configured (not yet running) :class:`FastMCP` server.
    """
    server: FastMCP = FastMCP(name)
    for skill in skills:
        if not skill.metadata.user_invocable:
            continue
        server.add_prompt(
            Prompt.from_function(
                _make_prompt_fn(skill),
                name=skill.name,
                description=skill.description,
            )
        )
    return server


def _skills_from_config() -> list[Skill]:
    """Union of skills across every agent definition in the loaded config."""
    from sgr_agent_core.agent_config import GlobalConfig
    from sgr_agent_core.agent_factory import AgentFactory

    by_name: dict[str, Skill] = {}
    for agent_def in GlobalConfig().agents.values():
        for skill in AgentFactory._resolve_skills(agent_def):
            by_name[skill.name] = skill
    return list(by_name.values())


def main() -> None:
    """Serve the project's skills as MCP prompts over stdio.

    Usage: ``python -m sgr_agent_core.skills.mcp_server --config config.yaml``
    """
    import argparse

    from sgr_agent_core.agent_config import GlobalConfig

    parser = argparse.ArgumentParser(
        prog="sgr-skills-mcp",
        description="Expose SGR skills as MCP prompts (slash commands) over stdio",
    )
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()

    GlobalConfig.from_yaml(args.config)
    server = build_skills_mcp_server(_skills_from_config())
    server.run()


if __name__ == "__main__":
    main()
