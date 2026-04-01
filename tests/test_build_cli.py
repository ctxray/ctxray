"""Tests for build CLI command."""

import json

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


class TestBuildCLI:
    def test_basic_build(self):
        result = runner.invoke(app, ["build", "fix the auth bug"])
        assert result.exit_code == 0
        assert "Built Prompt" in result.output

    def test_build_json(self):
        result = runner.invoke(app, ["build", "fix the auth bug", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "prompt" in data
        assert "score" in data
        assert "tier" in data
        assert "components_used" in data
        assert "suggestions" in data

    def test_build_with_file(self):
        result = runner.invoke(app, ["build", "fix the bug", "--file", "src/auth.ts"])
        assert result.exit_code == 0
        assert "src/auth.ts" in result.output

    def test_build_with_error(self):
        result = runner.invoke(app, ["build", "fix crash", "--error", "TypeError: null"])
        assert result.exit_code == 0
        assert "TypeError" in result.output

    def test_build_with_context(self):
        result = runner.invoke(app, ["build", "fix bug", "--context", "users get 401"])
        assert result.exit_code == 0

    def test_build_with_constraint(self):
        result = runner.invoke(app, ["build", "refactor", "--constraint", "keep tests"])
        assert result.exit_code == 0
        assert "keep tests" in result.output

    def test_build_with_multiple_constraints(self):
        result = runner.invoke(
            app,
            ["build", "refactor", "--constraint", "keep tests", "--constraint", "no new deps"],
        )
        assert result.exit_code == 0
        assert "keep tests" in result.output
        assert "no new deps" in result.output

    def test_build_with_role(self):
        result = runner.invoke(app, ["build", "review PR", "--role", "security engineer"])
        assert result.exit_code == 0
        assert "security engineer" in result.output

    def test_build_with_model_claude(self):
        result = runner.invoke(
            app,
            ["build", "fix bug", "--context", "auth", "--constraint", "x", "--model", "claude"],
        )
        assert result.exit_code == 0

    def test_build_with_model_gpt(self):
        result = runner.invoke(
            app,
            ["build", "fix bug", "--context", "auth", "--constraint", "x", "--model", "gpt"],
        )
        assert result.exit_code == 0

    def test_build_json_structure(self):
        result = runner.invoke(
            app,
            [
                "build",
                "fix auth",
                "--file",
                "src/auth.ts",
                "--error",
                "TypeError",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "files" in data["components_used"]
        assert "error" in data["components_used"]
        assert data["score"] > 0
        assert data["tier"] in ("DRAFT", "BASIC", "GOOD", "STRONG", "EXPERT")

    def test_build_shows_suggestion_hint(self):
        result = runner.invoke(app, ["build", "fix bug"])
        assert result.exit_code == 0
        assert "Try:" in result.output

    def test_build_help(self):
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "Build a well-structured prompt" in result.output

    def test_build_multiple_files(self):
        result = runner.invoke(
            app,
            ["build", "refactor", "--file", "a.py", "--file", "b.py"],
        )
        assert result.exit_code == 0
        assert "a.py" in result.output
        assert "b.py" in result.output

    def test_build_with_example(self):
        result = runner.invoke(
            app,
            ["build", "parse dates", "--example", "Input: 2026-01-01 → Output: Jan 1"],
        )
        assert result.exit_code == 0

    def test_build_with_output_format(self):
        result = runner.invoke(
            app,
            ["build", "analyze data", "--output-format", "JSON"],
        )
        assert result.exit_code == 0
