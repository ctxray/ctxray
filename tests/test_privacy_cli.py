"""CLI integration tests for ctxray privacy command."""

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


class TestPrivacyCli:
    def test_privacy_no_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "empty.db"))
        result = runner.invoke(app, ["privacy"])
        assert result.exit_code == 0
        assert "No prompt data" in result.output

    def test_privacy_with_data(self, tmp_path, monkeypatch):
        from ctxray.storage.db import PromptDB

        db_path = tmp_path / "test.db"
        monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
        db = PromptDB(db_path)
        db.insert_prompt("fix bug", source="claude-code", project="proj", session_id="s1")
        db.insert_prompt("add feat", source="chatgpt-export", project="proj", session_id="s2")

        result = runner.invoke(app, ["privacy"])
        assert result.exit_code == 0
        assert "Privacy Exposure" in result.output
        assert "claude-code" in result.output
        assert "chatgpt-export" in result.output

    def test_privacy_json_output(self, tmp_path, monkeypatch):
        import json

        from ctxray.storage.db import PromptDB

        db_path = tmp_path / "test.db"
        monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
        db = PromptDB(db_path)
        db.insert_prompt("test prompt", source="cursor", project="proj", session_id="s1")

        result = runner.invoke(app, ["privacy", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_prompts"] == 1
        assert data["cloud_prompts"] == 1
        assert len(data["sources"]) == 1
