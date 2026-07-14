"""Tests for the skills data model and loader (Layer 1)."""

from pathlib import Path

import pytest

from sgr_agent_core.skills import Skill, SkillError, SkillLoader, SkillMetadata


def _write_skill(root: Path, name: str, frontmatter: str, body: str = "Body text") -> Path:
    """Create a skill directory with a SKILL.md and return the directory."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
    return skill_dir


class TestSkillMetadata:
    """Validation rules for skill frontmatter metadata."""

    def test_valid_metadata(self):
        meta = SkillMetadata(name="pdf-processing", description="Process PDF files. Use when working with PDFs.")
        assert meta.name == "pdf-processing"
        assert meta.description.startswith("Process PDF")
        assert meta.allowed_tools == []
        assert meta.metadata == {}

    def test_name_too_long_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="a" * 65, description="ok")

    def test_name_invalid_chars_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="Bad_Name", description="ok")

    def test_name_reserved_word_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="claude-helper", description="ok")

    def test_name_xml_tag_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="foo<bar>", description="ok")

    def test_description_empty_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="foo", description="")

    def test_description_too_long_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="foo", description="x" * 1025)

    def test_description_xml_tag_rejected(self):
        with pytest.raises((ValueError, SkillError)):
            SkillMetadata(name="foo", description="uses <script> tags")

    def test_allowed_tools_alias(self):
        meta = SkillMetadata.model_validate({"name": "foo", "description": "bar", "allowed-tools": ["web_search_tool"]})
        assert meta.allowed_tools == ["web_search_tool"]


class TestSkillLoaderParse:
    """Parsing SKILL.md text into a Skill."""

    def test_parse_frontmatter_and_body(self):
        text = "---\nname: greet\ndescription: Greets people warmly.\n---\n\n# Greet\n\nSay hi.\n"
        skill = SkillLoader.parse(text)
        assert isinstance(skill, Skill)
        assert skill.name == "greet"
        assert skill.description == "Greets people warmly."
        assert "Say hi." in skill.body

    def test_parse_missing_frontmatter_raises(self):
        with pytest.raises(SkillError):
            SkillLoader.parse("# No frontmatter here\n")

    def test_parse_unterminated_frontmatter_raises(self):
        with pytest.raises(SkillError):
            SkillLoader.parse("---\nname: x\ndescription: y\n")

    def test_parse_missing_required_field_raises(self):
        with pytest.raises(SkillError):
            SkillLoader.parse("---\nname: x\n---\nbody")


class TestSkillLoaderLoadSkill:
    """Loading a skill from a directory."""

    def test_load_skill_from_dir(self, tmp_path):
        d = _write_skill(tmp_path, "greet", "name: greet\ndescription: Greets people.", "Say hi")
        skill = SkillLoader.load_skill(d)
        assert skill.name == "greet"
        assert skill.path == d
        assert "Say hi" in skill.body

    def test_load_skill_defaults_name_to_dir(self, tmp_path):
        # Frontmatter omits name -> loader fills it from directory name.
        d = tmp_path / "auto-named"
        d.mkdir()
        (d / "SKILL.md").write_text("---\ndescription: Auto named skill.\n---\nbody\n", encoding="utf-8")
        skill = SkillLoader.load_skill(d)
        assert skill.name == "auto-named"

    def test_load_skill_missing_file_raises(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        with pytest.raises(SkillError):
            SkillLoader.load_skill(d)


class TestSkillLoaderDiscover:
    """Discovering skills under a root directory."""

    def test_discover_multiple(self, tmp_path):
        _write_skill(tmp_path, "alpha", "name: alpha\ndescription: Alpha skill.")
        _write_skill(tmp_path, "beta", "name: beta\ndescription: Beta skill.")
        # A subdir without SKILL.md must be ignored.
        (tmp_path / "not-a-skill").mkdir()
        skills = SkillLoader.discover(tmp_path)
        names = sorted(s.name for s in skills)
        assert names == ["alpha", "beta"]

    def test_discover_missing_root_returns_empty(self, tmp_path):
        assert SkillLoader.discover(tmp_path / "does-not-exist") == []

    def test_discover_skips_malformed(self, tmp_path):
        _write_skill(tmp_path, "good", "name: good\ndescription: Good skill.")
        bad = tmp_path / "bad"
        bad.mkdir()
        (bad / "SKILL.md").write_text("no frontmatter at all\n", encoding="utf-8")
        skills = SkillLoader.discover(tmp_path)
        assert [s.name for s in skills] == ["good"]
