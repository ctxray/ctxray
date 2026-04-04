"""Tests for `ctxray repetition` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def _seed_db(tmp_path: Path) -> Path:
    """Create a DB with cross-session similar prompts."""
    from ctxray.storage.db import PromptDB

    db_path = tmp_path / "test.db"
    db = PromptDB(db_path)

    # Topic A: auth bug across 2 sessions
    db.insert_prompt(
        "fix the authentication bug in login.py please",
        source="claude-code",
        session_id="s1",
        timestamp="2026-03-01T10:00:00Z",
    )
    db.insert_prompt(
        "fix the authentication bug in login.py now",
        source="claude-code",
        session_id="s2",
        timestamp="2026-03-15T10:00:00Z",
    )
    # Unrelated prompt
    db.insert_prompt(
        "add pagination to the user list API endpoint",
        source="claude-code",
        session_id="s3",
        timestamp="2026-03-20T10:00:00Z",
    )
    return db_path


def test_repetition_no_data(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
    result = runner.invoke(app, ["repetition"])
    assert result.exit_code == 0
    assert "no cross-session" in result.output.lower()


def test_repetition_no_data_json(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
    result = runner.invoke(app, ["repetition", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["repetition_rate"] == 0.0
    assert data["recurring_topics"] == []


def test_repetition_with_data(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
    result = runner.invoke(app, ["repetition"])
    assert result.exit_code == 0


def test_repetition_json_output(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
    result = runner.invoke(app, ["repetition", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "repetition_rate" in data
    assert "recurring_topics" in data
    assert "total_prompts_analyzed" in data


def test_repetition_source_filter(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
    result = runner.invoke(app, ["repetition", "--source", "nonexistent", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_prompts_analyzed"] == 0


def test_repetition_last_option(tmp_path, monkeypatch):
    db_path = _seed_db(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))
    result = runner.invoke(app, ["repetition", "--last", "2", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_prompts_analyzed"] <= 2


def test_repetition_help():
    result = runner.invoke(app, ["repetition", "--help"])
    assert result.exit_code == 0
    assert "recurring" in result.output.lower() or "repetition" in result.output.lower()
