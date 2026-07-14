"""Shared helpers for treating skills as user-typed slash commands."""

from __future__ import annotations

from collections.abc import Iterable

from sgr_agent_core.skills.models import BaseSkill


def expand_skill_command(text: str, skills: Iterable[BaseSkill]) -> str | None:
    """Expand a ``/skill-name args`` message into the skill body + args.

    Args:
        text: Raw user message.
        skills: Skills available in the current context.

    Returns:
        The expanded prompt when the first token names a user-invocable skill,
        otherwise ``None`` (the message is not a skill command).
    """
    if not text.startswith("/"):
        return None
    head, _, rest = text[1:].partition(" ")
    skill = next((s for s in skills if s.name == head and s.metadata.user_invocable), None)
    if skill is None:
        return None
    body = skill.body.strip()
    remainder = rest.strip()
    return f"{body}\n\n{remainder}".strip() if remainder else body
