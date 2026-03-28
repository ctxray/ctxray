"""Tests for `reprompt agent` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


def _create_session_db(tmp_path: Path) -> Path:
    """Create a DB with session data by running through the adapter pipeline."""
    from reprompt.storage.db import PromptDB

    db_path = tmp_path / "test.db"
    db = PromptDB(db_path)

    # Insert some prompts with a session_id
    db.insert_prompt(
        "Fix the authentication bug in login.py",
        source="claude-code",
        project="test-project",
        session_id="test-session-001",
        timestamp="2026-03-28T10:00:00Z",
    )
    db.insert_prompt(
        "Now add unit tests for the auth module",
        source="claude-code",
        project="test-project",
        session_id="test-session-001",
        timestamp="2026-03-28T10:05:00Z",
    )

    # Also register a processed session with a real JSONL file
    jsonl_data = [
        {
            "type": "user",
            "timestamp": "2026-03-28T10:00:00Z",
            "message": {"role": "user", "content": "Fix the auth bug in login.py"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-03-28T10:00:05Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll fix the auth bug."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "src/auth.py"}},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "src/auth.py", "old_string": "x", "new_string": "y"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-03-28T10:01:00Z",
            "message": {"role": "user", "content": "Now add unit tests for the auth module"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-03-28T10:01:05Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Adding tests."},
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": "tests/test_auth.py", "content": "..."},
                    },
                ],
            },
        },
    ]

    # Write JSONL file
    session_file = tmp_path / "test-session-001.jsonl"
    with open(session_file, "w") as f:
        for entry in jsonl_data:
            f.write(json.dumps(entry) + "\n")

    # Register in processed_sessions (schema: file_path, processed_at, source)
    db.mark_session_processed(str(session_file), source="claude-code")

    return db_path


def test_agent_no_sessions(tmp_path, monkeypatch):
    """agent command with empty DB shows guidance message."""
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    result = runner.invoke(app, ["agent"])
    assert result.exit_code == 0
    assert "no" in result.output.lower() or "scan" in result.output.lower()


def test_agent_no_sessions_json(tmp_path, monkeypatch):
    """agent --json with empty DB returns empty JSON."""
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    result = runner.invoke(app, ["agent", "--json"])
    assert result.exit_code == 0
    assert result.output.strip() == "{}"


def test_agent_with_sessions(tmp_path, monkeypatch):
    """agent command renders report with session data."""
    db_path = _create_session_db(tmp_path)
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    result = runner.invoke(app, ["agent"])
    assert result.exit_code == 0
    assert "Agent Report" in result.output or "agent" in result.output.lower()


def test_agent_json_output(tmp_path, monkeypatch):
    """agent --json returns valid JSON with expected structure."""
    db_path = _create_session_db(tmp_path)
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    result = runner.invoke(app, ["agent", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert "sessions_analyzed" in data
    assert "tool_distribution" in data
    assert "error_loops" in data
    assert "sessions" in data
    assert data["sessions_analyzed"] >= 1


def test_agent_loops_only(tmp_path, monkeypatch):
    """agent --loops-only renders only loop section."""
    db_path = _create_session_db(tmp_path)
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    result = runner.invoke(app, ["agent", "--loops-only"])
    assert result.exit_code == 0
    # Clean session should show "No error loops"
    assert "no error loops" in result.output.lower() or "0" in result.output


def test_agent_source_filter(tmp_path, monkeypatch):
    """agent --source filters to specific adapter."""
    db_path = _create_session_db(tmp_path)
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    # Filter to nonexistent source
    result = runner.invoke(app, ["agent", "--source", "nonexistent"])
    assert result.exit_code == 0
    assert "no" in result.output.lower() or "{}" in result.output


def test_agent_last_option(tmp_path, monkeypatch):
    """agent --last N limits sessions analyzed."""
    db_path = _create_session_db(tmp_path)
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    result = runner.invoke(app, ["agent", "--last", "1", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["sessions_analyzed"] <= 1


def test_agent_help():
    """agent --help shows usage information."""
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    assert "error loops" in result.output.lower() or "workflow" in result.output.lower()
