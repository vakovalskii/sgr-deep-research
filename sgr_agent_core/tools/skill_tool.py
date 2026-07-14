"""The ``use_skill`` tool: progressive-disclosure level-2 skill expansion.

When the agent decides (from the system-prompt skills catalog) that a skill is
relevant, it calls ``use_skill`` with the skill name. The tool returns the
skill's full ``SKILL.md`` body, which the agent appends to the conversation and
follows for the rest of the run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pydantic import Field

from sgr_agent_core.base_tool import SystemBaseTool

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext


class SkillTool(SystemBaseTool):
    """Load the full instructions of an available skill by name."""

    tool_name: ClassVar[str] = "use_skill"
    description: ClassVar[str] = (
        "Load the full instructions of an available skill by name. "
        "Use this when a task matches a skill listed in AVAILABLE_SKILLS. "
        "Returns the skill's instructions to follow for the rest of the task."
    )

    skill_name: str = Field(description="Name of the skill to load (as shown in AVAILABLE_SKILLS)")

    async def __call__(self, context: "AgentContext", config: "AgentConfig", **kwargs) -> str:
        """Return the requested skill's body, or a helpful error listing the
        available skills."""
        skills = list(getattr(context, "available_skills", []) or [])
        skill = next((s for s in skills if s.name == self.skill_name), None)
        if skill is None:
            available = ", ".join(sorted(s.name for s in skills)) or "(none)"
            return f"Skill '{self.skill_name}' not found. Available skills: {available}"
        body = skill.body.strip() or "(this skill has no additional instructions)"
        return f'<SKILL name="{skill.name}">\n{body}\n</SKILL>'
