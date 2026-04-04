"""Tests for check CLI command."""

import json

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


class TestCheckCLI:
    def test_basic_check(self):
        result = runner.invoke(app, ["check", "fix the auth bug in login.ts"])
        assert result.exit_code == 0
        assert "Clarity" in result.output

    def test_check_json(self):
        result = runner.invoke(app, ["check", "fix the auth bug", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total" in data
        assert "tier" in data
        assert "lint_issues" in data
        assert "rewritten" in data
        assert "suggestions" in data
        assert "confirmations" in data

    def test_check_with_model(self):
        result = runner.invoke(app, ["check", "fix the auth bug", "--model", "claude"])
        assert result.exit_code == 0

    def test_check_with_max_tokens(self):
        result = runner.invoke(app, ["check", "fix bug", "--max-tokens", "1"])
        assert result.exit_code == 0

    def test_check_shows_dimensions(self):
        result = runner.invoke(app, ["check", "fix the auth bug in login.ts"])
        assert result.exit_code == 0
        assert "Context" in result.output
        assert "Position" in result.output
        assert "Structure" in result.output
        assert "Repetition" in result.output

    def test_check_shows_rewrite(self):
        result = runner.invoke(
            app,
            ["check", "I was wondering if you could maybe help me fix the bug"],
        )
        assert result.exit_code == 0
        # Should show rewrite section
        assert "Rewritten" in result.output or "Auto-rewrite" in result.output

    def test_check_short_prompt(self):
        result = runner.invoke(app, ["check", "fix it"])
        assert result.exit_code == 0

    def test_check_shows_suggestion_hint(self):
        result = runner.invoke(app, ["check", "fix the auth bug"])
        assert result.exit_code == 0
        assert "Try:" in result.output

    def test_check_help(self):
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "Full prompt diagnostic" in result.output

    def test_check_json_all_fields(self):
        result = runner.invoke(
            app,
            ["check", "fix the auth bug in login.ts where JWT expires", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] > 0
        assert data["tier"] in ("DRAFT", "BASIC", "GOOD", "STRONG", "EXPERT")
        assert data["word_count"] > 0
        assert data["token_count"] > 0
        assert isinstance(data["clarity"], (int, float))
        assert isinstance(data["context"], (int, float))
