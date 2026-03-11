"""Tests for reprompt lint CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


def test_lint_no_prompts(tmp_path, monkeypatch):
    """Lint with no data should exit cleanly."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["lint", "--path", str(tmp_path / "nonexistent")])
    assert result.exit_code == 0
    assert "No prompts found" in result.output


def test_lint_clean_prompts(tmp_path, monkeypatch):
    """Good prompts should produce no errors."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))

    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "fix the authentication bug in auth.py — login returns 401",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-10",
    )
    db.insert_prompt(
        "add pagination to search results with cursor-based navigation",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-10",
    )

    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 0
    assert "no issues found" in result.output


def test_lint_bad_prompts_exit_1(tmp_path, monkeypatch):
    """Prompts with errors should exit 1."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))

    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("fix it", source="test", project="test", session_id="s1", timestamp="")

    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 1


def test_lint_json_output(tmp_path, monkeypatch):
    """JSON output should contain violations structure."""
    import json

    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))

    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("fix it", source="test", project="test", session_id="s1", timestamp="")

    result = runner.invoke(app, ["lint", "--json"])
    data = json.loads(result.output)
    assert data["total_prompts"] == 1
    assert data["errors"] >= 1
    assert len(data["violations"]) >= 1


def test_lint_strict_mode(tmp_path, monkeypatch):
    """Strict mode should exit 1 on warnings too."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))

    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    # A prompt that triggers warning but not error (short but above min)
    db.insert_prompt(
        "fix the auth bug please",
        source="test",
        project="test",
        session_id="s1",
        timestamp="",
    )

    result = runner.invoke(app, ["lint", "--strict"])
    assert result.exit_code == 1
