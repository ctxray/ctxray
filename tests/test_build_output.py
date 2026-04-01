"""Tests for build terminal output."""

from reprompt.core.build import BuildResult
from reprompt.output.build_terminal import render_build


def _make_result(**kwargs):
    defaults = {
        "prompt": "Fix the auth bug.",
        "score": 45.0,
        "tier": "BASIC",
        "components_used": ["task"],
        "suggestions": ["Add --file to reference specific files (+6 pts)"],
    }
    defaults.update(kwargs)
    return BuildResult(**defaults)


class TestRenderBuild:
    def test_contains_prompt(self):
        output = render_build(_make_result())
        assert "Fix the auth bug" in output

    def test_contains_tier(self):
        output = render_build(_make_result(tier="GOOD", score=55.0))
        assert "GOOD" in output

    def test_contains_score(self):
        output = render_build(_make_result(score=67.0))
        assert "67" in output

    def test_shows_components(self):
        output = render_build(_make_result(components_used=["task", "files", "error"]))
        assert "task" in output
        assert "files" in output
        assert "error" in output

    def test_shows_suggestions(self):
        output = render_build(_make_result(suggestions=["Add --file (+6 pts)"]))
        assert "--file" in output

    def test_no_suggestions_when_empty(self):
        output = render_build(_make_result(suggestions=[]))
        assert "Add more" not in output

    def test_expert_tier(self):
        output = render_build(_make_result(tier="EXPERT", score=90.0))
        assert "EXPERT" in output

    def test_multiline_prompt(self):
        prompt = "Fix the auth bug.\n\nContext: users get 401 errors.\n\nConstraint: keep tests."
        output = render_build(_make_result(prompt=prompt))
        assert "Context" in output
        assert "Constraint" in output

    def test_long_prompt_panel(self):
        prompt = "Fix the authentication middleware.\n\n" + "Detail. " * 50
        output = render_build(_make_result(prompt=prompt))
        assert "Built Prompt" in output
