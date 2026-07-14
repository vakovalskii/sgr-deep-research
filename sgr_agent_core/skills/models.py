"""Data model for Agent Skills (Anthropic SKILL.md model).

A skill is a directory containing a ``SKILL.md`` file with YAML frontmatter
(``name`` + ``description`` required) and a markdown body. Frontmatter is
validated against the Anthropic Agent Skills spec rules.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    # Invocation gating (mirrors codex/Claude disable-model-invocation / user-invocable).
    model_invocable: bool = True
    user_invocable: bool = True

    @staticmethod
    def _coerce_bool(value: object) -> bool:
        """Coerce a YAML scalar to bool, honoring quoted strings like
        "false"."""
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        return bool(value)

    @model_validator(mode="before")
    @classmethod
    def _map_invocation_aliases(cls, data: object) -> object:
        """Translate Claude-style ``disable-model-invocation`` / ``user-
        invocable`` frontmatter into the internal ``model_invocable`` /
        ``user_invocable`` flags."""
        if isinstance(data, dict):
            data = dict(data)
            if "disable-model-invocation" in data:
                data["model_invocable"] = not cls._coerce_bool(data.pop("disable-model-invocation"))
            if "user-invocable" in data:
                data["user_invocable"] = cls._coerce_bool(data.pop("user-invocable"))
        return data

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("BaseSkill 'name' must be non-empty")
        if len(value) > NAME_MAX_LENGTH:
            raise ValueError(f"BaseSkill 'name' must be at most {NAME_MAX_LENGTH} characters")
        if "<" in value or ">" in value:
            raise ValueError("BaseSkill 'name' cannot contain XML tags")
        if not NAME_PATTERN.match(value):
            raise ValueError("BaseSkill 'name' must contain only lowercase letters, digits and hyphens")
        lowered = value.lower()
        for word in RESERVED_WORDS:
            if word in lowered:
                raise ValueError(f"BaseSkill 'name' cannot contain the reserved word '{word}'")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("BaseSkill 'description' must be non-empty")
        if len(value) > DESCRIPTION_MAX_LENGTH:
            raise ValueError(f"BaseSkill 'description' must be at most {DESCRIPTION_MAX_LENGTH} characters")
        if "<" in value or ">" in value:
            raise ValueError("BaseSkill 'description' cannot contain XML tags")
        return value


class BaseSkill(BaseModel):
    """A loaded skill: validated metadata plus the markdown body and source path."""

    metadata: SkillMetadata
    body: str = ""
    path: Path | None = None

    @property
    def name(self) -> str:
        """BaseSkill name (from metadata)."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """BaseSkill description (from metadata)."""
        return self.metadata.description

    @property
    def allowed_tools(self) -> list[str]:
        """Advisory list of tool names the skill uses."""
        return self.metadata.allowed_tools
