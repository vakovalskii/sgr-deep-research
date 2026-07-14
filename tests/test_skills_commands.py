"""Tests for the shared slash-command expansion helper and skill-root ordering."""

from pathlib import Path
from unittest.mock import Mock, patch

from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.skills import Skill, SkillMetadata, SkillsConfig, expand_skill_command


def _skill(name, description="A skill.", body="BODY", **kw):
    return Skill(metadata=SkillMetadata(name=name, description=description, **kw), body=body)


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
    def test_root_ordering_user_then_project_then_explicit(self, tmp_path):
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        cfg = SkillsConfig(paths=["extra", str(tmp_path / "abs")])
        fake_global = Mock()
        fake_global.config_dir = config_dir
        with patch("sgr_agent_core.agent_config.GlobalConfig", return_value=fake_global):
            roots = AgentFactory._default_skill_roots(cfg)

        assert roots[0] == Path.home() / ".sgr" / "skills"
        assert roots[1] == config_dir / "skills"
        # Relative explicit path resolved against config_dir; absolute kept as-is.
        assert roots[2] == config_dir / "extra"
        assert roots[3] == tmp_path / "abs"
