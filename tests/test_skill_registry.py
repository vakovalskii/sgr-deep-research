"""Tests for SkillRegistry and SkillsConfig (Layer 2)."""

from pathlib import Path

from sgr_agent_core.skills import BaseSkill, SkillMetadata, SkillRegistry
from sgr_agent_core.skills.config import SkillsConfig


def _skill(name: str, description: str = "A skill.") -> BaseSkill:
    return BaseSkill(metadata=SkillMetadata(name=name, description=description))


def _write_skill(root: Path, name: str, description: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\nbody\n", encoding="utf-8")


class TestSkillRegistry:
    def test_register_and_get(self):
        reg = SkillRegistry()
        reg.register(_skill("alpha"))
        assert reg.get("alpha").name == "alpha"
        assert reg.get("missing") is None
        assert "alpha" in reg

    def test_list_and_names_sorted(self):
        reg = SkillRegistry()
        reg.register(_skill("beta"))
        reg.register(_skill("alpha"))
        assert reg.names() == ["alpha", "beta"]
        assert [s.name for s in reg.list_items()] == ["alpha", "beta"]
        assert len(reg) == 2

    def test_register_overrides_same_name(self):
        reg = SkillRegistry()
        reg.register(_skill("dup", "first"))
        reg.register(_skill("dup", "second"))
        assert reg.get("dup").description == "second"
        assert len(reg) == 1

    def test_init_with_skills(self):
        reg = SkillRegistry([_skill("a"), _skill("b")])
        assert reg.names() == ["a", "b"]

    def test_clear(self):
        reg = SkillRegistry([_skill("a")])
        reg.clear()
        assert len(reg) == 0

    def test_load_from_paths(self, tmp_path):
        root1 = tmp_path / "root1"
        root2 = tmp_path / "root2"
        _write_skill(root1, "alpha", "Alpha.")
        _write_skill(root2, "beta", "Beta.")
        reg = SkillRegistry()
        reg.load_from_paths([root1, root2])
        assert reg.names() == ["alpha", "beta"]

    def test_load_from_paths_later_overrides_earlier(self, tmp_path):
        root1 = tmp_path / "root1"
        root2 = tmp_path / "root2"
        _write_skill(root1, "dup", "From root1.")
        _write_skill(root2, "dup", "From root2.")
        reg = SkillRegistry()
        reg.load_from_paths([root1, root2])
        assert reg.get("dup").description == "From root2."

    def test_load_from_paths_ignores_missing(self, tmp_path):
        reg = SkillRegistry()
        reg.load_from_paths([tmp_path / "nope"])
        assert len(reg) == 0


class TestSkillsConfig:
    def test_defaults(self):
        cfg = SkillsConfig()
        assert cfg.enabled is True
        assert cfg.paths == []
        assert cfg.include is None
        assert cfg.exclude is None

    def test_from_dict(self):
        cfg = SkillsConfig.model_validate({"enabled": False, "paths": ["./skills"], "include": ["a"], "exclude": ["b"]})
        assert cfg.enabled is False
        assert cfg.paths == ["./skills"]
        assert cfg.include == ["a"]
        assert cfg.exclude == ["b"]
