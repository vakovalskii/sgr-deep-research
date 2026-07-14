"""Agent Skills subsystem for SGR Agent Core.

Skills are directories containing a ``SKILL.md`` file (YAML frontmatter plus a
markdown body). They are auto-registered into the agent system prompt (name +
description) so the agent can invoke them autonomously, and can be surfaced as
commands over ACP/MCP.
"""

from sgr_agent_core.skills.loader import SKILL_FILE, SkillLoader
from sgr_agent_core.skills.models import Skill, SkillError, SkillMetadata

__all__ = [
    "Skill",
    "SkillError",
    "SkillMetadata",
    "SkillLoader",
    "SKILL_FILE",
]
