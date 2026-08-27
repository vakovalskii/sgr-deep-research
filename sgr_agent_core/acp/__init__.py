"""Agent Client Protocol (ACP) stdio integration for SGR Agent Core."""

from typing import TYPE_CHECKING

__all__ = ["SGRACPBridge", "extract_prompt_text"]

if TYPE_CHECKING:
    from sgr_agent_core.acp.bridge import SGRACPBridge, extract_prompt_text


def __getattr__(name: str):
    """Resolve bridge exports on first access.

    ``sgr_agent_core.acp.bridge`` needs ``agent-client-protocol`` from the
    ``[acp]`` extra. Deferring the import keeps ``sgr_agent_core.acp.__main__``
    importable on a core-only install, so the ``sgracp`` entrypoint can report
    the missing extra itself instead of dying inside the package import.
    """
    if name in __all__:
        from sgr_agent_core.acp import bridge

        return getattr(bridge, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
