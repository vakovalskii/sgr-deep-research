"""Internal utilities for config merging and tool helpers."""

from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def config_from_kwargs(config_class: type[T], base: T | None, kwargs: dict[str, Any]) -> T:
    """Build a config instance from base (optional) and kwargs; kwargs override
    base.

    Generic helper for any Pydantic config model. Used by tools to merge
    agent-level config with per-tool kwargs from the tools array (global or inline).

    Args:
        config_class: Pydantic model class to instantiate (e.g. SearchConfig).
        base: Existing config instance, or None to use only kwargs (with model defaults).
        kwargs: Overrides; keys present here override base. None values are skipped.

    Returns:
        New instance of config_class with merged values.
    """
    data = base.model_dump() if base is not None else {}
    data.update({k: v for k, v in kwargs.items() if v is not None})
    return config_class(**data)
