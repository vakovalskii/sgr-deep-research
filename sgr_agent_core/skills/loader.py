"""Loader that parses ``SKILL.md`` files and discovers skills on disk."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from sgr_agent_core.skills.models import BaseSkill, SkillError, SkillMetadata

logger = logging.getLogger(__name__)

SKILL_FILE = "SKILL.md"
# Guardrail: skip pathologically large SKILL.md files (they are injected into
# the model context on invocation). 1 MiB is far above any reasonable skill.
MAX_SKILL_FILE_BYTES = 1024 * 1024


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
    def parse(cls, text: str, *, path: Path | None = None, default_name: str | None = None) -> BaseSkill:
        """Parse ``SKILL.md`` text into a validated :class:`BaseSkill`.

        Args:
            text: Full ``SKILL.md`` content.
            path: Optional source path stored on the skill.
            default_name: Name to use when frontmatter omits ``name``
                (typically the skill directory name).

        Returns:
            A validated :class:`BaseSkill`.

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
        return BaseSkill(metadata=metadata, body=body, path=path)

    @classmethod
    def load_skill(cls, directory: Path) -> BaseSkill:
        """Load a single skill from a directory containing ``SKILL.md``.

        Args:
            directory: Directory holding the ``SKILL.md`` file.

        Returns:
            The loaded :class:`BaseSkill`.

        Raises:
            SkillError: If ``SKILL.md`` is missing or invalid.
        """
        directory = Path(directory)
        skill_file = directory / SKILL_FILE
        if not skill_file.is_file():
            raise SkillError(f"No {SKILL_FILE} found in {directory}")
        try:
            if skill_file.stat().st_size > MAX_SKILL_FILE_BYTES:
                raise SkillError(f"{skill_file} exceeds the maximum skill size of {MAX_SKILL_FILE_BYTES} bytes")
            text = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillError(f"Cannot read {skill_file}: {exc}") from exc
        except UnicodeDecodeError as exc:
            raise SkillError(f"{skill_file} is not valid UTF-8: {exc}") from exc
        return cls.parse(text, path=directory, default_name=directory.name)

    @classmethod
    def discover(cls, root: Path) -> list[BaseSkill]:
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
        skills: list[BaseSkill] = []
        try:
            entries = sorted(root.iterdir())
        except OSError as exc:
            logger.warning("Cannot list skill root %s: %s", root, exc)
            return []
        for entry in entries:
            if not entry.is_dir():
                continue
            if not (entry / SKILL_FILE).is_file():
                continue
            try:
                skills.append(cls.load_skill(entry))
            except SkillError as exc:
                logger.warning("Skipping malformed skill in %s: %s", entry, exc)
        return skills
