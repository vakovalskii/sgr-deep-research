"""Loader that parses ``SKILL.md`` files and discovers skills on disk."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from sgr_agent_core.skills.models import Skill, SkillError, SkillMetadata

logger = logging.getLogger(__name__)

SKILL_FILE = "SKILL.md"


class SkillLoader:
    """Parse and discover skills from the filesystem.

    A skill lives in its own directory that contains a ``SKILL.md`` file with
    YAML frontmatter and a markdown body (progressive disclosure level 2).
    """

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict, str]:
        """Split raw ``SKILL.md`` text into a frontmatter dict and a body.

        Args:
            text: Full ``SKILL.md`` content.

        Returns:
            Tuple of (frontmatter mapping, markdown body).

        Raises:
            SkillError: If the leading YAML frontmatter block is missing or
                unterminated, or is not a mapping.
        """
        stripped = text.lstrip("﻿")
        if not stripped.startswith("---"):
            raise SkillError("SKILL.md must start with a YAML frontmatter block delimited by '---'")

        lines = stripped.splitlines()
        end_index: int | None = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break
        if end_index is None:
            raise SkillError("SKILL.md frontmatter block is not terminated by '---'")

        frontmatter_text = "\n".join(lines[1:end_index])
        body = "\n".join(lines[end_index + 1 :]).strip()
        try:
            data = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as exc:
            raise SkillError(f"Invalid YAML in SKILL.md frontmatter: {exc}") from exc
        if not isinstance(data, dict):
            raise SkillError("SKILL.md frontmatter must be a YAML mapping")
        return data, body

    @classmethod
    def parse(cls, text: str, *, path: Path | None = None, default_name: str | None = None) -> Skill:
        """Parse ``SKILL.md`` text into a validated :class:`Skill`.

        Args:
            text: Full ``SKILL.md`` content.
            path: Optional source path stored on the skill.
            default_name: Name to use when frontmatter omits ``name``
                (typically the skill directory name).

        Returns:
            A validated :class:`Skill`.

        Raises:
            SkillError: If frontmatter is missing, malformed, or fails validation.
        """
        data, body = cls._split_frontmatter(text)
        if "name" not in data and default_name is not None:
            data["name"] = default_name
        try:
            metadata = SkillMetadata.model_validate(data)
        except ValidationError as exc:
            raise SkillError(f"Invalid skill metadata: {exc}") from exc
        return Skill(metadata=metadata, body=body, path=path)

    @classmethod
    def load_skill(cls, directory: Path) -> Skill:
        """Load a single skill from a directory containing ``SKILL.md``.

        Args:
            directory: Directory holding the ``SKILL.md`` file.

        Returns:
            The loaded :class:`Skill`.

        Raises:
            SkillError: If ``SKILL.md`` is missing or invalid.
        """
        directory = Path(directory)
        skill_file = directory / SKILL_FILE
        if not skill_file.is_file():
            raise SkillError(f"No {SKILL_FILE} found in {directory}")
        text = skill_file.read_text(encoding="utf-8")
        return cls.parse(text, path=directory, default_name=directory.name)

    @classmethod
    def discover(cls, root: Path) -> list[Skill]:
        """Discover all skills in immediate subdirectories of ``root``.

        Malformed skills are logged and skipped so one bad skill never breaks
        discovery of the rest.

        Args:
            root: Directory whose immediate subdirectories may be skills.

        Returns:
            List of successfully loaded skills, sorted by name.
        """
        root = Path(root)
        if not root.is_dir():
            return []
        skills: list[Skill] = []
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / SKILL_FILE).is_file():
                continue
            try:
                skills.append(cls.load_skill(entry))
            except SkillError as exc:
                logger.warning("Skipping malformed skill in %s: %s", entry, exc)
        return skills
