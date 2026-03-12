# tests/test_insights_cli.py
"""Tests for reprompt insights CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


class TestInsightsCommand:
    def test_insights_no_data(self):
        """insights with empty DB should not crash."""
        result = runner.invoke(app, ["insights"])
        assert result.exit_code == 0

    def test_insights_json_output(self):
        result = runner.invoke(app, ["insights", "--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "prompt_count" in data
