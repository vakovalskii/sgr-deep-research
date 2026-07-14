"""Data model for Agent Skills (Anthropic SKILL.md model).

A skill is a directory containing a ``SKILL.md`` file with YAML frontmatter
(``name`` + ``description`` required) and a markdown body. Frontmatter is
validated against the Anthropic Agent Skills spec rules.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 1024
NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")
RESERVED_WORDS = ("anthropic", "claude")


class SkillError(Exception):
    """Raised when a skill cannot be parsed, validated, or loaded."""


class SkillMetadata(BaseModel):
    """Validated frontmatter of a ``SKILL.md`` file.

    Enforces the Anthropic Agent Skills spec: ``name`` is lowercase letters,
    digits and hyphens up to 64 chars (no XML tags, no reserved words) and
    ``description`` is a non-empty string up to 1024 chars with no XML tags.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    license: str | None = None
    allowed_tools: list[str] = Field(default_factory=list, alias="allowed-tools")
    metadata: dict = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Skill 'name' must be non-empty")
        if len(value) > NAME_MAX_LENGTH:
            raise ValueError(f"Skill 'name' must be at most {NAME_MAX_LENGTH} characters")
        if "<" in value or ">" in value:
            raise ValueError("Skill 'name' cannot contain XML tags")
        if not NAME_PATTERN.match(value):
            raise ValueError("Skill 'name' must contain only lowercase letters, digits and hyphens")
        lowered = value.lower()
        for word in RESERVED_WORDS:
            if word in lowered:
                raise ValueError(f"Skill 'name' cannot contain the reserved word '{word}'")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Skill 'description' must be non-empty")
        if len(value) > DESCRIPTION_MAX_LENGTH:
            raise ValueError(f"Skill 'description' must be at most {DESCRIPTION_MAX_LENGTH} characters")
        if "<" in value or ">" in value:
            raise ValueError("Skill 'description' cannot contain XML tags")
        return value


class Skill(BaseModel):
    """A loaded skill: validated metadata plus the markdown body and source path."""

    metadata: SkillMetadata
    body: str = ""
    path: Path | None = None

    @property
    def name(self) -> str:
        """Skill name (from metadata)."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """Skill description (from metadata)."""
        return self.metadata.description

    @property
    def allowed_tools(self) -> list[str]:
        """Advisory list of tool names the skill uses."""
        return self.metadata.allowed_tools
