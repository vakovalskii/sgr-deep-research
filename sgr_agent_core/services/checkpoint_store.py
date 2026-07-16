"""Checkpoint stores for persisting and restoring agent snapshots.

A store keeps :class:`AgentCheckpoint` objects keyed by agent id. Two backends
are provided:

* :class:`InMemoryCheckpointStore` — process-local history (default).
* :class:`FileCheckpointStore` — JSON files on disk that survive a restart.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from sgr_agent_core.models import AgentCheckpoint

logger = logging.getLogger(__name__)


class BaseCheckpointStore(ABC):
    """Abstract checkpoint store.

    Subclasses implement the raw persistence primitives (``save``, ``list``,
    ``delete``, ``agent_ids``); the lookup helpers are derived from them.
    """

    @abstractmethod
    def save(self, checkpoint: AgentCheckpoint) -> None:
        """Persist a checkpoint, replacing any existing one with the same step."""

    @abstractmethod
    def list(self, agent_id: str) -> list[AgentCheckpoint]:
        """Return all checkpoints for an agent, ordered by step ascending."""

    @abstractmethod
    def delete(self, agent_id: str) -> None:
        """Remove all checkpoints for an agent."""

    @abstractmethod
    def agent_ids(self) -> list[str]:
        """Return the ids of all agents that have at least one checkpoint."""

    def get(self, agent_id: str, step: int) -> AgentCheckpoint | None:
        """Return the checkpoint for a specific step, or None if absent."""
        for checkpoint in self.list(agent_id):
            if checkpoint.step == step:
                return checkpoint
        return None

    def latest(self, agent_id: str) -> AgentCheckpoint | None:
        """Return the highest-step checkpoint for an agent, or None."""
        checkpoints = self.list(agent_id)
        return checkpoints[-1] if checkpoints else None

    def find_by_session(self, session_id: str) -> list[AgentCheckpoint]:
        """Return all checkpoints tagged with ``session_id``, ordered by step."""
        found: list[AgentCheckpoint] = []
        for agent_id in self.agent_ids():
            found.extend(cp for cp in self.list(agent_id) if cp.session_id == session_id)
        found.sort(key=lambda cp: cp.step)
        return found


class InMemoryCheckpointStore(BaseCheckpointStore):
    """Keep checkpoints in memory, keyed by agent id then step.

    Args:
        max_history: When set, only the most recent ``max_history`` steps per
            agent are retained (a ring buffer); older ones are evicted on save.
    """

    def __init__(self, max_history: int | None = None) -> None:
        self._max_history = max_history
        self._store: dict[str, dict[int, AgentCheckpoint]] = {}

    def save(self, checkpoint: AgentCheckpoint) -> None:
        steps = self._store.setdefault(checkpoint.agent_id, {})
        steps[checkpoint.step] = checkpoint
        self._evict(steps)

    def _evict(self, steps: dict[int, AgentCheckpoint]) -> None:
        if self._max_history is None:
            return
        while len(steps) > self._max_history:
            del steps[min(steps)]

    def list(self, agent_id: str) -> list[AgentCheckpoint]:
        steps = self._store.get(agent_id, {})
        return [steps[step] for step in sorted(steps)]

    def delete(self, agent_id: str) -> None:
        self._store.pop(agent_id, None)

    def agent_ids(self) -> list[str]:
        return list(self._store.keys())


class FileCheckpointStore(BaseCheckpointStore):
    """Persist checkpoints as JSON files under ``{root}/{agent_id}/{step}.json``.

    Args:
        root: Directory to store checkpoints in (created on demand).
        max_history: When set, only the most recent ``max_history`` steps per
            agent are kept on disk; older files are deleted on save.
    """

    def __init__(self, root: str, max_history: int | None = None) -> None:
        self._root = Path(root)
        self._max_history = max_history

    def _agent_dir(self, agent_id: str) -> Path:
        return self._root / agent_id

    @staticmethod
    def _step_file(agent_dir: Path, step: int) -> Path:
        return agent_dir / f"{step:08d}.json"

    def save(self, checkpoint: AgentCheckpoint) -> None:
        agent_dir = self._agent_dir(checkpoint.agent_id)
        agent_dir.mkdir(parents=True, exist_ok=True)
        self._step_file(agent_dir, checkpoint.step).write_text(
            checkpoint.model_dump_json(indent=2), encoding="utf-8"
        )
        self._evict(agent_dir)

    def _evict(self, agent_dir: Path) -> None:
        if self._max_history is None:
            return
        files = sorted(agent_dir.glob("*.json"))
        for stale in files[: -self._max_history]:
            stale.unlink(missing_ok=True)

    def list(self, agent_id: str) -> list[AgentCheckpoint]:
        agent_dir = self._agent_dir(agent_id)
        if not agent_dir.is_dir():
            return []
        checkpoints: list[AgentCheckpoint] = []
        for path in sorted(agent_dir.glob("*.json")):
            try:
                checkpoints.append(AgentCheckpoint.model_validate_json(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Skipping unreadable checkpoint %s: %s", path, exc)
        checkpoints.sort(key=lambda cp: cp.step)
        return checkpoints

    def delete(self, agent_id: str) -> None:
        agent_dir = self._agent_dir(agent_id)
        if not agent_dir.is_dir():
            return
        for path in agent_dir.glob("*.json"):
            path.unlink(missing_ok=True)
        agent_dir.rmdir()

    def agent_ids(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return [child.name for child in self._root.iterdir() if child.is_dir()]
