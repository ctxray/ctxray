"""Tests for deprecated command aliases."""

from __future__ import annotations

import re
import tempfile

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestDeprecatedTemplateCommands:
    def test_old_save_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(
                app,
                ["save", "Fix the auth bug"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        assert "Saved template" in result.output

    def test_old_templates_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["templates"], env={"CTXRAY_DB_PATH": f.name})
        assert result.exit_code == 0

    def test_old_use_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            runner.invoke(
                app,
                ["save", "Hello world", "--name", "hw"],
                env={"CTXRAY_DB_PATH": f.name},
            )
            result = runner.invoke(
                app,
                ["use", "hw"],
                env={"CTXRAY_DB_PATH": f.name},
            )
        assert result.exit_code == 0
        assert "Hello world" in _strip_ansi(result.output)


class TestDeprecatedAnalyticsCommands:
    def test_old_effectiveness_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["effectiveness"], env={"CTXRAY_DB_PATH": f.name})
        assert result.exit_code == 0

    def test_old_merge_view_still_works(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["merge-view"], env={"CTXRAY_DB_PATH": f.name})
        assert result.exit_code == 0
