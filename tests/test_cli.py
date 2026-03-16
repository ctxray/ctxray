"""Tests for CLI entry point."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "reprompt" in result.output.lower()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "reprompt" in result.output
    # Check version format (e.g. "reprompt 1.0.0")
    assert "reprompt 1." in result.output


def test_status_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "0" in result.output


def test_scan_no_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["scan", "--path", str(tmp_path / "empty")])
    assert result.exit_code == 0


def test_scan_with_source(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(
        app, ["scan", "--source", "claude-code", "--path", str(tmp_path / "empty")]
    )
    assert result.exit_code == 0
    assert "Scan complete" in result.output


def test_report_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0


def test_report_json_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["report", "--format", "json"])
    assert result.exit_code == 0


def test_library_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0


def test_purge(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["purge"])
    assert result.exit_code == 0
    assert "Purged" in result.output


def test_search_no_results(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["search", "nonexistent"])
    assert result.exit_code == 0
    assert "No prompts matching" in result.output


def test_search_finds_matching(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    # Insert a prompt directly
    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("fix the authentication bug in login handler", source="claude-code")
    db.insert_prompt("add unit tests for payment module", source="claude-code")

    result = runner.invoke(app, ["search", "authentication"])
    assert result.exit_code == 0
    assert "authentication" in result.output
    assert "1 results" in result.output


def test_search_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    for i in range(5):
        db.insert_prompt(f"test prompt number {i} about debugging", source="claude-code")

    result = runner.invoke(app, ["search", "debugging", "--limit", "2"])
    assert result.exit_code == 0
    assert "2 results" in result.output


def test_install_hook_registers_in_settings(tmp_path, monkeypatch):
    """install-hook should write to settings.json, not just a shell script."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()

    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "registered" in result.output

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "hooks" in settings
    assert "Stop" in settings["hooks"]
    assert any(
        h.get("command") == "reprompt scan --source claude-code" for h in settings["hooks"]["Stop"]
    )


def test_install_hook_idempotent(tmp_path, monkeypatch):
    """Running install-hook twice should not duplicate the entry."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()

    runner.invoke(app, ["install-hook"])
    result = runner.invoke(app, ["install-hook"])
    assert "already registered" in result.output

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    stop_hooks = settings["hooks"]["Stop"]
    matching = [h for h in stop_hooks if h.get("command") == "reprompt scan --source claude-code"]
    assert len(matching) == 1


def test_install_hook_preserves_existing_settings(tmp_path, monkeypatch):
    """install-hook should not clobber existing settings."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()
    existing = {"permissions": {"allow": ["Bash"]}}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(existing))

    runner.invoke(app, ["install-hook"])

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == ["Bash"]
    assert "hooks" in settings


def test_scan_shows_counts(tmp_path, monkeypatch):
    """Scan output should include the count fields."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    # Create a fake session
    sessions = tmp_path / "sessions" / "-Users-test-projects-app"
    sessions.mkdir(parents=True)
    session_file = sessions / "session-001.jsonl"
    msg = {
        "type": "user",
        "message": {
            "role": "user",
            "content": "implement the search feature with full-text search",
        },
        "timestamp": "2026-01-15T10:00:00Z",
    }
    session_file.write_text(json.dumps(msg) + "\n")

    result = runner.invoke(
        app, ["scan", "--source", "claude-code", "--path", str(tmp_path / "sessions")]
    )
    assert result.exit_code == 0
    assert "Sessions scanned" in result.output
    assert "Prompts found" in result.output
