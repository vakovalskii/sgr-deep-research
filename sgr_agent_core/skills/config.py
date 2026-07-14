"""Configuration model for the skills subsystem."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillsConfig(BaseModel):
    """Agent/global configuration for skill discovery and activation.

    Attributes:
        enabled: Master switch; when False no skills are loaded or injected.
        paths: Skill root directories to scan. When set, these replace the
            default roots; otherwise the default roots are used.
        include: If set, only skills whose name is in this list are activated.
        exclude: Skills whose name is in this list are dropped.
    """

    enabled: bool = True
    paths: list[str] = Field(default_factory=list)
    include: list[str] | None = None
    exclude: list[str] | None = None
