"""Tests for explain CLI command."""

import json

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


class TestExplainCLI:
    def test_basic_explain(self):
        result = runner.invoke(app, ["explain", "fix the auth bug in login.ts"])
        assert result.exit_code == 0
        assert "Analysis" in result.output

    def test_explain_json(self):
        result = runner.invoke(app, ["explain", "fix the auth bug", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "score" in data
        assert "tier" in data
        assert "summary" in data
        assert "strengths" in data
        assert "weaknesses" in data
        assert "tips" in data

    def test_explain_shows_tier(self):
        result = runner.invoke(app, ["explain", "fix the auth bug"])
        assert result.exit_code == 0

    def test_explain_short_prompt(self):
        result = runner.invoke(app, ["explain", "fix it"])
        assert result.exit_code == 0

    def test_explain_good_prompt(self):
        result = runner.invoke(
            app,
            [
                "explain",
                "Fix the authentication bug in src/auth.ts. "
                "Error: JWT expired. Don't change tests.",
            ],
        )
        assert result.exit_code == 0

    def test_explain_shows_hint(self):
        result = runner.invoke(app, ["explain", "fix the auth bug"])
        assert result.exit_code == 0
        assert "Try:" in result.output

    def test_explain_help(self):
        result = runner.invoke(app, ["explain", "--help"])
        assert result.exit_code == 0
        assert "Explain what makes a prompt good or bad" in result.output
