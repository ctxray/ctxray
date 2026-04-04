"""Tests for ctxray template sub-command group."""

from __future__ import annotations

import json
import re
import tempfile

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (Rich color output on CI)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestTemplateSave:
    def test_save_basic(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(
                app,
                ["template", "save", "Fix the auth bug in login.py"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        assert "Saved template" in result.output

    def test_save_with_name_and_category(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(
                app,
                [
                    "template",
                    "save",
                    "Debug the API endpoint",
                    "--name",
                    "api-debug",
                    "--category",
                    "debugging",
                ],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        assert "api-debug" in result.output

    def test_save_json(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(
                app,
                ["template", "save", "Test prompt", "--json"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "name" in data
        assert "category" in data


class TestTemplateList:
    def test_list_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["template", "list"], env={"CTXRAY_DB_PATH": f.name})
        assert result.exit_code == 0
        assert "No templates" in _strip_ansi(result.output)

    def test_list_with_data(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            runner.invoke(
                app,
                ["template", "save", "Fix the auth bug"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            result = runner.invoke(app, ["template", "list"], env={"CTXRAY_DB_PATH": f.name})
        assert result.exit_code == 0
        assert "1 saved" in _strip_ansi(result.output) or "1" in result.output

    def test_list_json(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            runner.invoke(
                app,
                ["template", "save", "Test prompt"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            result = runner.invoke(
                app, ["template", "list", "--json"], env={"CTXRAY_DB_PATH": f.name}
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_filter_category(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            runner.invoke(
                app,
                ["template", "save", "Debug X", "--category", "debugging"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            runner.invoke(
                app,
                ["template", "save", "Explain Y", "--category", "learning"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            result = runner.invoke(
                app,
                ["template", "list", "--category", "debugging", "--json"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1


class TestTemplateUse:
    def test_use_basic(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            runner.invoke(
                app,
                ["template", "save", "Fix {component} in {file}", "--name", "fix-tpl"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            result = runner.invoke(
                app,
                ["template", "use", "fix-tpl", "component=auth", "file=login.py"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        assert "Fix auth in login.py" in _strip_ansi(result.output)

    def test_use_not_found(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(
                app,
                ["template", "use", "nonexistent"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 1

    def test_use_json(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            runner.invoke(
                app,
                ["template", "save", "Hello world", "--name", "hw"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            result = runner.invoke(
                app,
                ["template", "use", "hw", "--json"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "rendered" in data
        assert data["rendered"] == "Hello world"


class TestTemplateDefault:
    def test_template_no_subcommand_shows_list(self):
        """Running `ctxray template` with no subcommand should show template list."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["template"], env={"CTXRAY_DB_PATH": f.name})
        assert result.exit_code == 0
        assert (
            "No templates" in _strip_ansi(result.output)
            or "template" in _strip_ansi(result.output).lower()
        )


class TestTemplateHelp:
    def test_template_help_shows_subcommands(self):
        result = runner.invoke(app, ["template", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "save" in output
        assert "list" in output
        assert "use" in output
