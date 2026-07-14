"""Configuration model for the skills subsystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillsConfig(BaseModel):
    """Agent/global configuration for skill discovery and rendering.

    Attributes:
        enabled: Master switch; when False no skills are loaded or injected.
        paths: Extra skill root directories to scan (in addition to defaults).
        include: If set, only skills whose name is in this list are kept.
        exclude: Skills whose name is in this list are dropped.
        max_desc_chars: Per-entry description cap in the system-prompt listing
            (progressive disclosure level 1 budget).
    """

    enabled: bool = True
    paths: list[str] = Field(default_factory=list)
    include: list[str] | None = None
    exclude: list[str] | None = None
    max_desc_chars: int = 500
