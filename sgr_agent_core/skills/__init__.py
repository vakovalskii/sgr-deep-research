"""Agent Skills subsystem for SGR Agent Core.

Skills are directories containing a ``SKILL.md`` file (YAML frontmatter plus a
markdown body). They are auto-registered into the agent system prompt (name +
description) so the agent can invoke them autonomously, and can be surfaced as
user commands over ACP.
"""

from sgr_agent_core.skills.commands import (
    find_referenced_skills,
    inject_referenced_skills,
    render_skill_body,
)
from sgr_agent_core.skills.config import SkillsConfig
from sgr_agent_core.skills.loader import SKILL_FILE, SkillLoader
from sgr_agent_core.skills.models import BaseSkill, SkillError, SkillMetadata
from sgr_agent_core.skills.registry import SkillRegistry
from sgr_agent_core.skills.rendering import render_available_skills

__all__ = [
    "BaseSkill",
    "SkillError",
    "SkillMetadata",
    "SkillLoader",
    "SkillRegistry",
    "SkillsConfig",
    "render_available_skills",
    "find_referenced_skills",
    "inject_referenced_skills",
    "render_skill_body",
    "SKILL_FILE",
]
