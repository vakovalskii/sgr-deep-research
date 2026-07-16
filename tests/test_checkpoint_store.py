"""Tests for checkpoint stores (in-memory and file backends)."""

import pytest

from sgr_agent_core.models import AgentCheckpoint
from sgr_agent_core.services.checkpoint_store import (
    FileCheckpointStore,
    InMemoryCheckpointStore,
)


def _checkpoint(agent_id: str, step: int, session_id: str | None = None) -> AgentCheckpoint:
    return AgentCheckpoint(
        agent_id=agent_id,
        def_name="sgr_agent",
        step=step,
        session_id=session_id,
        task_messages=[{"role": "user", "content": "task"}],
        conversation=[{"role": "system", "content": f"step {step}"}],
        context={"iteration": step, "state": "researching"},
    )


class _StoreContract:
    """Shared behavior that every checkpoint store must satisfy."""

    def make_store(self):
        raise NotImplementedError

    def test_save_and_list_ordered_by_step(self):
        store = self.make_store()
        store.save(_checkpoint("a", 2))
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("a", 3))

        steps = [cp.step for cp in store.list("a")]
        assert steps == [1, 2, 3]

    def test_list_unknown_agent_is_empty(self):
        assert self.make_store().list("missing") == []

    def test_get_by_step(self):
        store = self.make_store()
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("a", 2))

        assert store.get("a", 2).step == 2
        assert store.get("a", 99) is None

    def test_latest_returns_highest_step(self):
        store = self.make_store()
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("a", 5))
        store.save(_checkpoint("a", 3))

        assert store.latest("a").step == 5
        assert store.latest("missing") is None

    def test_save_same_step_replaces(self):
        store = self.make_store()
        store.save(_checkpoint("a", 1))
        replacement = _checkpoint("a", 1)
        replacement.conversation = [{"role": "system", "content": "replaced"}]
        store.save(replacement)

        assert len(store.list("a")) == 1
        assert store.get("a", 1).conversation[0]["content"] == "replaced"

    def test_delete_removes_agent(self):
        store = self.make_store()
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("b", 1))

        store.delete("a")

        assert store.list("a") == []
        assert store.list("b")

    def test_agent_ids(self):
        store = self.make_store()
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("b", 1))

        assert set(store.agent_ids()) == {"a", "b"}

    def test_find_by_session(self):
        store = self.make_store()
        store.save(_checkpoint("a", 1, session_id="s1"))
        store.save(_checkpoint("a", 2, session_id="s1"))
        store.save(_checkpoint("b", 1, session_id="s2"))

        found = store.find_by_session("s1")
        assert {cp.agent_id for cp in found} == {"a"}
        assert [cp.step for cp in found] == [1, 2]
        assert store.find_by_session("missing") == []


class TestInMemoryCheckpointStore(_StoreContract):
    def make_store(self):
        return InMemoryCheckpointStore()

    def test_max_history_evicts_oldest(self):
        store = InMemoryCheckpointStore(max_history=2)
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("a", 2))
        store.save(_checkpoint("a", 3))

        steps = [cp.step for cp in store.list("a")]
        assert steps == [2, 3]


class TestFileCheckpointStore(_StoreContract):
    @pytest.fixture(autouse=True)
    def _tmp(self, tmp_path):
        self._dir = tmp_path / "checkpoints"

    def make_store(self):
        return FileCheckpointStore(str(self._dir))

    def test_persists_across_instances(self):
        """A new store over the same directory must see previously saved data."""
        store = FileCheckpointStore(str(self._dir))
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("a", 2))

        reopened = FileCheckpointStore(str(self._dir))
        assert [cp.step for cp in reopened.list("a")] == [1, 2]
        assert reopened.latest("a").context["iteration"] == 2

    def test_max_history_evicts_oldest_on_disk(self):
        store = FileCheckpointStore(str(self._dir), max_history=2)
        store.save(_checkpoint("a", 1))
        store.save(_checkpoint("a", 2))
        store.save(_checkpoint("a", 3))

        assert [cp.step for cp in FileCheckpointStore(str(self._dir)).list("a")] == [2, 3]
