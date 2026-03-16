"""Tests for the 'reprompt wrapped' CLI command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


class TestWrappedCLI:
    def test_wrapped_runs(self, tmp_path, monkeypatch):
        """wrapped command exits 0 with empty DB."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["wrapped"])
        assert result.exit_code == 0

    def test_wrapped_json(self, tmp_path, monkeypatch):
        """--json outputs valid JSON with expected keys."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["wrapped", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "persona" in data
        assert "avg_scores" in data

    def test_wrapped_html_flag(self, tmp_path, monkeypatch):
        """--html saves an HTML card to the given file."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        out_file = tmp_path / "wrapped.html"
        result = runner.invoke(app, ["wrapped", "--html", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "<html" in content.lower()
