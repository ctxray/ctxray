"""Tests for CLI entry point."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "reprompt" in result.output.lower()


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
    result = runner.invoke(app, ["scan", "--source", "claude-code", "--path", str(tmp_path / "empty")])
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


def test_scan_shows_counts(tmp_path, monkeypatch):
    """Scan output should include the count fields."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    # Create a fake session
    sessions = tmp_path / "sessions" / "-Users-test-projects-app"
    sessions.mkdir(parents=True)
    session_file = sessions / "session-001.jsonl"
    msg = {"type": "user", "message": {"role": "user", "content": "implement the search feature with full-text search"},
           "timestamp": "2026-01-15T10:00:00Z"}
    session_file.write_text(json.dumps(msg) + "\n")

    result = runner.invoke(app, ["scan", "--source", "claude-code", "--path", str(tmp_path / "sessions")])
    assert result.exit_code == 0
    assert "Sessions scanned" in result.output
    assert "Prompts found" in result.output
