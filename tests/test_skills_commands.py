"""Tests for the shared slash-command expansion helper and skill-root
ordering."""

from pathlib import Path

from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.skills import BaseSkill, SkillMetadata, SkillsConfig, expand_skill_command


def _skill(name, description="A skill.", body="BODY", **kw):
    return BaseSkill(metadata=SkillMetadata(name=name, description=description, **kw), body=body)


class TestExpandSkillCommand:
    def test_matching_command(self):
        out = expand_skill_command("/greet say hi", [_skill("greet", body="Greet warmly.")])
        assert out is not None
        assert "Greet warmly." in out and "say hi" in out

    def test_no_args(self):
        out = expand_skill_command("/greet", [_skill("greet", body="Greet warmly.")])
        assert out == "Greet warmly."

    def test_unknown_command(self):
        assert expand_skill_command("/nope x", [_skill("greet")]) is None

    def test_non_command(self):
        assert expand_skill_command("hello there", [_skill("greet")]) is None

    def test_non_user_invocable_not_expanded(self):
        assert expand_skill_command("/greet", [_skill("greet", user_invocable=False)]) is None


class TestDefaultSkillRoots:
    def test_defaults_when_no_paths(self):
        roots = AgentFactory._default_skill_roots(SkillsConfig())
        assert roots == [Path.cwd() / ".agent" / "skills", Path.home() / ".agent" / "skills"]

    def test_explicit_paths_override_defaults(self, tmp_path):
        cfg = SkillsConfig(paths=["extra", str(tmp_path / "abs")])
        roots = AgentFactory._default_skill_roots(cfg)
        # Relative path resolved against CWD; absolute kept as-is; defaults dropped.
        assert roots == [Path.cwd() / "extra", tmp_path / "abs"]
