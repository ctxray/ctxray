# tests/test_score_cli.py
"""Tests for reprompt score and compare CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


class TestScoreCommand:
    def test_score_basic(self):
        result = runner.invoke(app, ["score", "Fix the bug in auth.py"])
        assert result.exit_code == 0
        assert "Score" in result.output or "score" in result.output

    def test_score_shows_breakdown(self):
        result = runner.invoke(
            app, ["score", "Fix the TypeError in auth/login.py:42 when token expires"]
        )
        assert result.exit_code == 0
        assert "Structure" in result.output or "structure" in result.output
        assert "Context" in result.output or "context" in result.output

    def test_score_shows_suggestions(self):
        result = runner.invoke(app, ["score", "Fix it"])
        assert result.exit_code == 0
        # Should have suggestions for a vague prompt
        assert (
            "Suggestion" in result.output
            or "suggestion" in result.output
            or "\u2192" in result.output
        )

    def test_score_json_output(self):
        result = runner.invoke(app, ["score", "--json", "Fix the bug"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "total" in data
        assert "suggestions" in data

    def test_score_empty_prompt(self):
        result = runner.invoke(app, ["score", ""])
        assert result.exit_code == 0


class TestCompareCommand:
    def test_compare_two_prompts(self):
        result = runner.invoke(
            app,
            [
                "compare",
                "Fix the bug",
                "Fix the TypeError in auth/login.py:42 \u2014 token validation fails on expired tokens",  # noqa: E501
            ],
        )
        assert result.exit_code == 0
        assert "Prompt A" in result.output or "prompt_a" in result.output
        assert "Prompt B" in result.output or "prompt_b" in result.output

    def test_compare_json_output(self):
        result = runner.invoke(
            app,
            [
                "compare",
                "--json",
                "Fix bug",
                "Fix the TypeError in auth.py:42",
            ],
        )
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "prompt_a" in data
        assert "prompt_b" in data
