"""Render the model-facing skills catalog (progressive disclosure level 1).

Mirrors the codex ``render_available_skills_body`` pattern: a short block listing
each model-invocable skill's name + (budgeted) description, followed by a
"how to use" instruction telling the agent to load a skill's full body via the
``use_skill`` tool. This is what makes skills autonomously invocable.
"""

from __future__ import annotations

from collections.abc import Iterable

from sgr_agent_core.skills.models import BaseSkill

DEFAULT_MAX_DESC_CHARS = 500


def _truncate(text: str, max_chars: int) -> str:
    """Truncate ``text`` to ``max_chars`` with an ellipsis if it overflows."""
    text = " ".join(text.split())
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


def _global_max_desc_chars() -> int:
    """Read the description budget from global execution settings (lazy)."""
    try:
        from sgr_agent_core.agent_config import GlobalConfig

        return GlobalConfig().execution.max_skill_desc_chars
    except Exception:  # noqa: BLE001 - fall back to the default outside a loaded config
        return DEFAULT_MAX_DESC_CHARS


def render_available_skills(skills: Iterable[BaseSkill], max_desc_chars: int | None = None) -> str:
    """Render the skills listing block injected into the system prompt.

    Only model-invocable skills are listed. Returns an empty string when there
    are none, so the system prompt stays unchanged for skill-less agents.

    Args:
        skills: Skills available to the agent.
        max_desc_chars: Per-entry description cap (level-1 budget). Defaults to
            the global ``execution.max_skill_desc_chars`` setting.

    Returns:
        A markdown block (or empty string).
    """
    if max_desc_chars is None:
        max_desc_chars = _global_max_desc_chars()
    listed = [s for s in skills if s.metadata.model_invocable]
    if not listed:
        return ""

    lines = [
        "<AVAILABLE_SKILLS>",
        "A skill is a set of instructions loaded on demand from a SKILL.md source.",
        "The skills below are available this turn. Each entry shows a name and description.",
        "",
        "### Available Skills",
    ]
    for skill in listed:
        lines.append(f"- {skill.name}: {_truncate(skill.description, max_desc_chars)}")
    lines.extend(
        [
            "",
            "### How to use Skills",
            "- If the user names a skill, or the task clearly matches a skill's description above,",
            "  call the `use_skill` tool with that skill's name to load its full instructions.",
            "- Read the loaded instructions completely before acting on them.",
            "- Only load a skill when it is relevant; do not load skills you do not need.",
            "</AVAILABLE_SKILLS>",
        ]
    )
    return "\n".join(lines)
