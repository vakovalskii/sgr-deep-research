"""In-memory catalog of loaded skills.

Unlike ``ToolRegistry`` (populated via ``__init_subclass__`` at import time),
skills are *data* loaded from the filesystem, so ``SkillRegistry`` is an
instance-based catalog populated by scanning skill roots.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from sgr_agent_core.skills.loader import SkillLoader
from sgr_agent_core.skills.models import Skill


class SkillRegistry:
    """Ordered, name-keyed catalog of :class:`Skill` objects.

    Registering a skill with an existing name overrides the previous
    one, so later skill roots take precedence over earlier ones
    (personal over builtin, project over personal, explicit paths last).
    """

    def __init__(self, skills: Iterable[Skill] | None = None) -> None:
        self._skills: dict[str, Skill] = {}
        if skills:
            for skill in skills:
                self.register(skill)

    def register(self, skill: Skill) -> None:
        """Add or replace a skill by name."""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Return the skill with ``name`` or ``None`` if not registered."""
        return self._skills.get(name)

    def names(self) -> list[str]:
        """Return all registered skill names, sorted."""
        return sorted(self._skills.keys())

    def list_items(self) -> list[Skill]:
        """Return all registered skills, sorted by name."""
        return [self._skills[name] for name in self.names()]

    def load_from_paths(self, paths: Iterable[Path | str]) -> None:
        """Discover and register skills from each root directory in order.

        Missing roots are ignored. Skills discovered in later roots override
        same-named skills from earlier roots.

        Args:
            paths: Skill root directories to scan.
        """
        for path in paths:
            for skill in SkillLoader.discover(Path(path)):
                self.register(skill)

    def clear(self) -> None:
        """Remove all registered skills."""
        self._skills.clear()

    def __contains__(self, name: object) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)
