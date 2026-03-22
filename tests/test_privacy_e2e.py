"""E2E test: privacy in report + standalone privacy command."""

import json

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


class TestPrivacyE2E:
    def test_full_flow(self, tmp_path, monkeypatch):
        """Scan some prompts, then verify privacy appears in report and standalone."""
        from reprompt.storage.db import PromptDB

        db_path = tmp_path / "e2e.db"
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

        # Seed DB with prompts from multiple sources
        db = PromptDB(db_path)
        db.insert_prompt(
            "fix the auth bug in login.py",
            source="claude-code",
            project="myapp",
            session_id="s1",
        )
        db.insert_prompt(
            "refactor the database layer",
            source="cursor",
            project="myapp",
            session_id="s2",
        )
        db.insert_prompt(
            "explain how React hooks work",
            source="chatgpt-export",
            project="learn",
            session_id="s3",
        )
        db.insert_prompt(
            "add unit tests for parser",
            source="aider",
            project="myapp",
            session_id="s4",
        )

        # Report should include privacy section
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "Privacy Exposure" in result.output

        # Standalone privacy command
        result = runner.invoke(app, ["privacy"])
        assert result.exit_code == 0
        assert "claude-code" in result.output
        assert "aider" in result.output

        # JSON output
        result = runner.invoke(app, ["privacy", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_prompts"] == 4
        assert data["cloud_prompts"] == 3  # claude-code, cursor, chatgpt-export
        assert data["local_prompts"] == 1  # aider
        assert data["training_exposed"] == 1  # chatgpt-export (opt-out)
