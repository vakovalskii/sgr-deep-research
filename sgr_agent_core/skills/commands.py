"""Detect ``/skill-name`` references in user messages and inject skill bodies.

This is the explicit, user-driven counterpart to autonomous invocation via the
``use_skill`` tool: if a user message references a skill by name with a leading
slash (e.g. ``/citation-style``), that skill's full body is injected into the
prompt so the agent follows it. Applied centrally in ``AgentFactory.create`` so
every entrypoint (ACP, CLI, OpenAI server) behaves the same.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from sgr_agent_core.skills.models import BaseSkill

# A reference is a "/name" token preceded by start-of-string, whitespace, or a
# common opening delimiter (quote, backtick, paren, bracket, asterisk, brace),
# and NOT followed by another "/". The possessive quantifier + "(?!/)" reject
# filesystem paths like "/etc/hosts"; the lookbehind rejects URLs like
# "http://x/greet" and inline "a/greet".
SKILL_REF_RE = re.compile(r"""(?<![^\s"'(\[`*{])/([a-z0-9][a-z0-9-]*+)(?!/)""")
# Closing delimiter inside a skill body is neutralized so a body cannot break
# out of its <SKILL> wrapper (skills are trusted content, but be defensive).
_CLOSING_TAG_RE = re.compile(r"</\s*SKILL\s*>", re.IGNORECASE)


def render_skill_body(skill: BaseSkill) -> str:
    """Wrap a skill's body in a delimited block for injection into the
    prompt."""
    body = skill.body.strip() or "(this skill has no additional instructions)"
    body = _CLOSING_TAG_RE.sub("< /SKILL>", body)
    return f'<SKILL name="{skill.name}">\n{body}\n</SKILL>'


def _message_text(content: Any) -> str:
    """Extract user-visible text from a message ``content`` (str or parts
    list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return " ".join(parts)
    return ""


def find_referenced_skills(text: str, skills: Sequence[BaseSkill]) -> list[BaseSkill]:
    """Return user-invocable skills referenced as ``/name`` in ``text`` (in
    order)."""
    invocable = {s.name: s for s in skills if s.metadata.user_invocable}
    seen: set[str] = set()
    found: list[BaseSkill] = []
    for match in SKILL_REF_RE.finditer(text or ""):
        name = match.group(1)
        if name in invocable and name not in seen:
            seen.add(name)
            found.append(invocable[name])
    return found


def inject_referenced_skills(task_messages: list[dict], skills: Sequence[BaseSkill]) -> list[dict]:
    """Inject bodies of skills referenced in the last user message.

    Scans the last ``user`` message for ``/skill-name`` references and, for each
    match, inserts a user message with the skill body right before it. Returns a
    new list; the input is left unmodified. No references (or no skills) returns
    the original list unchanged.
    """
    if not skills or not task_messages:
        return task_messages
    idx = next((i for i in range(len(task_messages) - 1, -1, -1) if task_messages[i].get("role") == "user"), None)
    if idx is None:
        return task_messages
    referenced = find_referenced_skills(_message_text(task_messages[idx].get("content")), skills)
    if not referenced:
        return task_messages
    block = "\n\n".join(render_skill_body(s) for s in referenced)
    new_messages = list(task_messages)
    new_messages.insert(idx, {"role": "user", "content": block})
    return new_messages
