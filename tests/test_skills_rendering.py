"""Tests for the system-prompt skills listing renderer (Layer 3)."""

from sgr_agent_core.skills import Skill, SkillMetadata
from sgr_agent_core.skills.rendering import render_available_skills


def _skill(name, description, **kw):
    return Skill(metadata=SkillMetadata(name=name, description=description, **kw))


class TestRenderAvailableSkills:
    def test_empty_returns_empty_string(self):
        assert render_available_skills([]) == ""

    def test_lists_name_and_description(self):
        out = render_available_skills([_skill("pdf-processing", "Process PDF files. Use for PDFs.")])
        assert "pdf-processing" in out
        assert "Process PDF files. Use for PDFs." in out
        # Codex-style block header and how-to guidance for autonomous invocation.
        assert "Skills" in out
        assert "use_skill" in out

    def test_multiple_skills_listed(self):
        out = render_available_skills([_skill("alpha", "Alpha."), _skill("beta", "Beta.")])
        assert "alpha" in out and "beta" in out

    def test_description_truncated_to_budget(self):
        long_desc = "x" * 300
        out = render_available_skills([_skill("big", long_desc)], max_desc_chars=50)
        # The rendered description must be capped (with an ellipsis), not full length.
        assert "x" * 300 not in out
        assert "…" in out

    def test_excludes_non_model_invocable(self):
        out = render_available_skills(
            [
                _skill("visible", "Visible skill."),
                _skill("hidden", "Hidden skill.", model_invocable=False),
            ]
        )
        assert "visible" in out
        assert "hidden" not in out

    def test_all_hidden_returns_empty(self):
        out = render_available_skills([_skill("hidden", "Hidden.", model_invocable=False)])
        assert out == ""
