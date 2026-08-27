"""Helpers for optional dependencies shipped as packaging extras.

The core package installs only what every SGR agent needs (pydantic,
PyYAML, openai, httpx). Integrations — MCP, Tavily search, the HTTP
server, ACP and Langfuse — live behind extras, so their imports must
happen at call time and fail with a message that names the extra to
install.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

# Top-level module name -> extra that provides it.
_EXTRA_BY_MODULE: dict[str, str] = {
    "fastmcp": "mcp",
    "jambo": "mcp",
    "tavily": "search",
    "fastapi": "server",
    "uvicorn": "server",
    "acp": "acp",
    "langfuse": "langfuse",
}


class MissingDependencyError(ImportError):
    """Raised when a feature needs a package that is not installed.

    Subclasses ``ImportError`` so callers that already catch import
    failures keep working.
    """


def install_hint(module: str) -> str:
    """Return the ``pip install`` command that provides ``module``."""
    extra = _EXTRA_BY_MODULE.get(module.split(".")[0])
    target = f"sgr-agent-core[{extra}]" if extra else module
    return f"pip install '{target}'"


def missing_dependency_error(module: str, *, feature: str) -> MissingDependencyError:
    """Build the error for a missing optional dependency."""
    return MissingDependencyError(
        f"{feature} requires the optional '{module}' package, which is not installed.\n"
        f"Install it with:  {install_hint(module)}"
    )


def require(module: str, *, feature: str) -> ModuleType:
    """Import an optional dependency or explain which extra provides it.

    Args:
        module: Importable module name (e.g. ``"tavily"``, ``"fastmcp.mcp_config"``).
        feature: Human-readable name of what needs it, used in the error message.

    Returns:
        The imported module.

    Raises:
        MissingDependencyError: If the module cannot be imported.
    """
    try:
        return import_module(module)
    except ImportError as exc:
        raise missing_dependency_error(module, feature=feature) from exc
