"""OverlayFS manager for RunCommandTool filesystem isolation.

Manages OverlayFS mounts created at server startup and unmounted at
shutdown.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import ClassVar

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.tools.run_command_tool import (
    RunCommandToolConfig,
    _collect_allowed_binaries,
    _resolve_command_path,
)

logger = logging.getLogger(__name__)


def _get_run_command_config_candidates(config: GlobalConfig) -> list[RunCommandToolConfig]:
    """Collect RunCommandTool config from global tools and from each agent's
    tools.

    Returns list of RunCommandToolConfig: from global tool definition (if present)
    and from each agent that uses RunCommandTool (effective kwargs per agent).
    """
    candidates: list[RunCommandToolConfig] = []
    runcommand_def = config.tools.get("run_command_tool") or config.tools.get("runcommandtool")
    if runcommand_def and hasattr(runcommand_def, "tool_kwargs"):
        tool_config_dict = runcommand_def.tool_kwargs()
        candidates.append(RunCommandToolConfig(**tool_config_dict))
    for agent_def in config.agents.values():
        _, tool_configs = AgentFactory._resolve_tools_with_configs(agent_def.tools)
        if "runcommandtool" in tool_configs:
            candidates.append(RunCommandToolConfig(**tool_configs["runcommandtool"]))
    return candidates


class OverlayFSManager:
    """Manages OverlayFS mounts for RunCommandTool.

    Creates overlay filesystems at startup based on tool configuration
    and unmounts them at shutdown.
    """

    _instance: ClassVar["OverlayFSManager | None"] = None
    _overlay_mounts: ClassVar[dict[str, str]] = {}  # original_dir -> merged_path
    _overlay_info: ClassVar[dict[str, str]] = {}  # merged_path -> "upper:work"
    _temp_base: ClassVar[Path | None] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize_overlayfs(cls, include_paths: set[str], exclude_paths: set[str]) -> dict[str, str]:
        """Initialize OverlayFS mounts for given include/exclude paths.

        Args:
            include_paths: Set of paths to include (allowed)
            exclude_paths: Set of paths to exclude (hidden via whiteout)

        Returns:
            Dict mapping original directory -> merged mount path
        """
        if cls._temp_base is None:
            cls._temp_base = Path(await asyncio.to_thread(tempfile.mkdtemp, prefix="runcommand_overlay_"))
            logger.info("Created OverlayFS base directory: %s", cls._temp_base)

        # Group paths by their parent directories
        dir_to_binaries: dict[str, set[str]] = {}
        for bin_path in include_paths | exclude_paths:
            bin_path_obj = Path(bin_path)
            parent_dir = str(bin_path_obj.parent)
            if parent_dir not in dir_to_binaries:
                dir_to_binaries[parent_dir] = set()
            dir_to_binaries[parent_dir].add(bin_path)

        for original_dir, binaries in dir_to_binaries.items():
            if original_dir in cls._overlay_mounts:
                # Already mounted, skip
                continue

            # Create temp directories for this overlay
            dir_name = original_dir.replace("/", "_").lstrip("_")
            lower_dir = Path(original_dir)
            upper_dir = cls._temp_base / f"upper_{dir_name}"
            work_dir = cls._temp_base / f"work_{dir_name}"
            merged_dir = cls._temp_base / f"merged_{dir_name}"

            # Create directories (blocking I/O in thread pool)
            await asyncio.to_thread(upper_dir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(work_dir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(merged_dir.mkdir, parents=True, exist_ok=True)

            # Create whiteout files for exclude_paths in this directory
            for bin_path in binaries:
                if bin_path in exclude_paths:
                    bin_name = Path(bin_path).name
                    whiteout_path = upper_dir / f".wh.{bin_name}"

                    def _ensure_whiteout() -> None:
                        if not whiteout_path.exists():
                            try:
                                os.mknod(
                                    str(whiteout_path),
                                    0o000 | 0o200000,
                                    os.makedev(0, 0),
                                )
                            except (OSError, PermissionError):
                                whiteout_path.touch()

                    await asyncio.to_thread(_ensure_whiteout)

            # Mount overlayfs via async subprocess
            try:
                lower_str = str(await asyncio.to_thread(lambda: lower_dir.resolve()))
                upper_str = str(await asyncio.to_thread(lambda: upper_dir.resolve()))
                work_str = str(await asyncio.to_thread(lambda: work_dir.resolve()))
                merged_str = str(await asyncio.to_thread(lambda: merged_dir.resolve()))

                mount_cmd = [
                    "mount",
                    "-t",
                    "overlay",
                    "overlay",
                    "-o",
                    f"lowerdir={lower_str},upperdir={upper_str},workdir={work_str}",
                    merged_str,
                ]

                process = await asyncio.create_subprocess_exec(
                    *mount_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()
                if process.returncode != 0:
                    logger.warning(
                        "Failed to mount overlayfs for %s: %s",
                        original_dir,
                        stderr.decode("utf-8", errors="replace") if stderr else "",
                    )
                    continue

                cls._overlay_mounts[original_dir] = merged_str
                cls._overlay_info[merged_str] = f"{upper_str}:{work_str}"
                logger.info("Mounted OverlayFS: %s -> %s", original_dir, merged_str)

            except Exception:
                logger.exception("Error creating overlayfs for %s", original_dir)

        return cls._overlay_mounts.copy()

    @classmethod
    def get_overlay_mounts(cls) -> dict[str, str]:
        """Get current overlay mounts.

        Returns:
            Dict mapping original directory -> merged mount path
        """
        return cls._overlay_mounts.copy()

    @classmethod
    async def initialize_from_config(cls) -> None:
        """Initialize OverlayFS for RunCommandTool from GlobalConfig.

        If RunCommandTool is used with mode safe anywhere (global or any
        agent), runs overlay init once at startup.
        include_paths/exclude_paths may be unset; then no overlay mounts
        are created but manager is ready.
        """
        try:
            config = GlobalConfig()
            candidates = _get_run_command_config_candidates(config)
            tool_config = None
            for c in candidates:
                if c.mode == "safe":
                    tool_config = c
                    break
            if not tool_config:
                if candidates:
                    logger.warning(
                        "RunCommandTool is configured only with unsafe mode; OverlayFS will not be initialized.",
                    )
                return

            if not tool_config.workspace_path or not str(tool_config.workspace_path).strip():
                base_dir = getattr(config, "config_dir", None) or Path.cwd()
                try:
                    base_path = Path(base_dir)
                except TypeError:
                    base_path = Path.cwd()
                workspace_dir = base_path / "workspace"
                try:
                    await asyncio.to_thread(workspace_dir.mkdir, parents=True, exist_ok=True)
                except Exception:
                    logger.exception("Failed to create default workspace directory at %s", workspace_dir)
                    return
                logger.warning(
                    "RunCommandTool workspace_path is not set; using default workspace directory: %s",
                    workspace_dir,
                )
                tool_config.workspace_path = str(workspace_dir)

            # Collect include/exclude paths (may be empty if user did not set them)
            include_paths, _ = _collect_allowed_binaries(tool_config.include_paths, tool_config.exclude_paths)
            exclude_paths: set[str] = set()
            if tool_config.exclude_paths:
                for excl_item in tool_config.exclude_paths:
                    excl_path = _resolve_command_path(excl_item) if "/" not in excl_item else None
                    if not excl_path:
                        try:
                            p = Path(excl_item).resolve()
                            if p.is_file() or p.exists():
                                excl_path = str(p)
                        except Exception:
                            continue
                    if excl_path:
                        try:
                            if Path(excl_path).exists() and Path(excl_path).is_file():
                                exclude_paths.add(excl_path)
                        except Exception:
                            pass

            mounts = await cls.initialize_overlayfs(include_paths, exclude_paths)
            if mounts:
                logger.info("Initialized OverlayFS for RunCommandTool: %d mounts", len(mounts))
        except Exception:
            logger.exception("Failed to initialize OverlayFS for RunCommandTool")

    @classmethod
    async def cleanup(cls) -> None:
        """Unmount all overlay filesystems and clean up temporary
        directories."""
        if not cls._overlay_mounts and cls._temp_base is None:
            logger.warning("OverlayFSManager.cleanup called but OverlayFS was not initialized")
            return
        for merged_path in list(cls._overlay_mounts.values()):
            try:
                process = await asyncio.create_subprocess_exec(
                    "umount",
                    merged_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                await process.communicate()
                if process.returncode != 0:
                    logger.warning("Failed to unmount OverlayFS: %s", merged_path)
                else:
                    logger.info("Unmounted OverlayFS: %s", merged_path)
            except Exception:
                logger.warning("Failed to unmount OverlayFS: %s", merged_path)

        cls._overlay_mounts.clear()
        cls._overlay_info.clear()

        if cls._temp_base and cls._temp_base.exists():
            try:
                await asyncio.to_thread(shutil.rmtree, cls._temp_base)
                logger.info("Cleaned up OverlayFS base directory: %s", cls._temp_base)
            except Exception:
                logger.warning("Failed to clean up OverlayFS base directory: %s", cls._temp_base)
            cls._temp_base = None
