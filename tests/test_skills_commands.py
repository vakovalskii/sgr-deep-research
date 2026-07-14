"""Tests for slash-skill reference detection/injection and skill-root
ordering."""

from pathlib import Path

from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.skills import BaseSkill, SkillMetadata, SkillsConfig
from sgr_agent_core.skills.commands import (
    find_referenced_skills,
    inject_referenced_skills,
    render_skill_body,
)


def _skill(name, description="A skill.", body="BODY", **kw):
    return BaseSkill(metadata=SkillMetadata(name=name, description=description, **kw), body=body)


class TestFindReferencedSkills:
    def test_single_reference(self):
        assert [s.name for s in find_referenced_skills("/greet hi", [_skill("greet")])] == ["greet"]

    def test_reference_mid_sentence(self):
        skills = [_skill("greet"), _skill("concise-answer")]
        found = find_referenced_skills("please use /greet and then /concise-answer", skills)
        assert [s.name for s in found] == ["greet", "concise-answer"]

    def test_non_user_invocable_not_matched(self):
        assert find_referenced_skills("/hidden", [_skill("hidden", user_invocable=False)]) == []

    def test_url_slash_not_matched(self):
        # A slash preceded by a non-space (e.g. inside a URL) is not a reference.
        assert find_referenced_skills("see http://example.com/greet", [_skill("greet")]) == []

    def test_filesystem_path_not_matched(self):
        # Path-like "/a/b" tokens must not be treated as skill references.
        skills = [_skill("etc"), _skill("opt"), _skill("usr")]
        assert find_referenced_skills("please read /etc/hosts", skills) == []
        assert find_referenced_skills("files live under /opt/data", skills) == []
        assert find_referenced_skills("/usr/local/bin", skills) == []

    def test_quoted_and_delimited_references_matched(self):
        skill = [_skill("greet")]
        for text in ("`/greet`", '"/greet"', "(/greet)", "[/greet]"):
            assert [s.name for s in find_referenced_skills(text, skill)] == ["greet"], text

    def test_unknown_reference_ignored(self):
        assert find_referenced_skills("/nope", [_skill("greet")]) == []

    def test_no_reference(self):
        assert find_referenced_skills("just a normal message", [_skill("greet")]) == []

    def test_duplicate_reference_once(self):
        assert [s.name for s in find_referenced_skills("/greet /greet", [_skill("greet")])] == ["greet"]


class TestRenderSkillBody:
    def test_wraps_body(self):
        out = render_skill_body(_skill("greet", body="Do the thing."))
        assert out == '<SKILL name="greet">\nDo the thing.\n</SKILL>'

    def test_empty_body_placeholder(self):
        out = render_skill_body(_skill("greet", body="   "))
        assert "no additional instructions" in out

    def test_neutralizes_closing_delimiter(self):
        out = render_skill_body(_skill("greet", body="text </SKILL> more"))
        # Only the outer wrapper's closing tag should remain a real </SKILL>.
        assert out.count("</SKILL>") == 1


class TestInjectReferencedSkills:
    def test_injects_body_before_last_user_message(self):
        msgs = [{"role": "user", "content": "/greet say hi"}]
        out = inject_referenced_skills(msgs, [_skill("greet", body="Greet warmly.")])
        assert len(out) == 2
        assert "Greet warmly." in out[0]["content"]
        assert out[1] == {"role": "user", "content": "/greet say hi"}

    def test_no_reference_returns_unchanged(self):
        msgs = [{"role": "user", "content": "hello"}]
        assert inject_referenced_skills(msgs, [_skill("greet")]) == msgs

    def test_no_skills_returns_unchanged(self):
        msgs = [{"role": "user", "content": "/greet"}]
        assert inject_referenced_skills(msgs, []) == msgs

    def test_picks_last_user_message_in_history(self):
        msgs = [
            {"role": "user", "content": "old question"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "/greet now"},
        ]
        out = inject_referenced_skills(msgs, [_skill("greet", body="B")])
        assert len(out) == 4
        # injected right before the last user message (index 2)
        assert "B" in out[2]["content"]
        assert out[3]["content"] == "/greet now"

    def test_multimodal_content_text_part(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "look /greet"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
                ],
            }
        ]
        out = inject_referenced_skills(msgs, [_skill("greet", body="Greet!")])
        assert len(out) == 2
        assert "Greet!" in out[0]["content"]

    def test_does_not_mutate_input(self):
        msgs = [{"role": "user", "content": "/greet"}]
        inject_referenced_skills(msgs, [_skill("greet", body="B")])
        assert len(msgs) == 1


class TestDefaultSkillRoots:
    def test_defaults_when_no_paths(self):
        roots = AgentFactory._default_skill_roots(SkillsConfig())
        assert roots == [Path.cwd() / ".agent" / "skills", Path.home() / ".agent" / "skills"]

    def test_explicit_paths_override_defaults(self, tmp_path):
        cfg = SkillsConfig(paths=["extra", str(tmp_path / "abs")])
        roots = AgentFactory._default_skill_roots(cfg)
        assert roots == [Path.cwd() / "extra", tmp_path / "abs"]
