"""Tests for `ctxray sessions` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def _create_db_with_quality(tmp_path: Path) -> Path:
    """Create a DB with session metadata and quality scores."""
    from ctxray.storage.db import PromptDB

    db_path = tmp_path / "test.db"
    db = PromptDB(db_path)

    # Insert two sessions
    db.upsert_session_meta(
        session_id="sess-good",
        source="claude-code",
        project="test-project",
        start_time="2026-03-28T10:00:00Z",
        end_time="2026-03-28T10:30:00Z",
        duration_seconds=1800,
        prompt_count=10,
        tool_call_count=20,
        error_count=1,
        final_status="success",
        avg_prompt_length=200.0,
        effectiveness_score=0.85,
    )
    db.upsert_session_quality(
        session_id="sess-good",
        quality_score=78.5,
        prompt_quality_score=80.0,
        efficiency_score=75.0,
        focus_score=60.0,
        outcome_score=85.0,
        session_type="implementation",
        quality_insight="Solid session",
    )

    db.upsert_session_meta(
        session_id="sess-rough",
        source="cursor",
        project="test-project",
        start_time="2026-03-28T09:00:00Z",
        end_time="2026-03-28T09:45:00Z",
        duration_seconds=2700,
        prompt_count=25,
        tool_call_count=40,
        error_count=12,
        final_status="error",
        avg_prompt_length=100.0,
        effectiveness_score=0.35,
    )
    db.upsert_session_quality(
        session_id="sess-rough",
        quality_score=32.0,
        prompt_quality_score=40.0,
        efficiency_score=25.0,
        has_abandonment=True,
        has_escalation=True,
        stall_turns=5,
        session_type="debugging",
        quality_insight="Ended with unresolved errors",
    )

    return db_path


def test_sessions_no_data(tmp_path, monkeypatch):
    """sessions command with empty DB shows guidance."""
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions"])
    assert result.exit_code == 0
    assert "no sessions" in result.output.lower() or "scan" in result.output.lower()


def test_sessions_no_data_json(tmp_path, monkeypatch):
    """sessions --json with empty DB returns empty list."""
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_sessions_with_data(tmp_path, monkeypatch):
    """sessions command renders table with scored sessions."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions"])
    assert result.exit_code == 0
    assert "Session Quality" in result.output
    assert "sess-good" in result.output
    assert "sess-rough" in result.output


def test_sessions_json_output(tmp_path, monkeypatch):
    """sessions --json returns valid JSON with quality fields."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    assert data[0]["quality_score"] is not None
    assert "session_id" in data[0]
    assert "quality_insight" in data[0]


def test_sessions_source_filter(tmp_path, monkeypatch):
    """sessions --source filters to specific adapter."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--source", "cursor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["source"] == "cursor"


def test_sessions_last_option(tmp_path, monkeypatch):
    """sessions --last N limits results."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--last", "1", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1


def test_sessions_detail(tmp_path, monkeypatch):
    """sessions --detail shows single session breakdown."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--detail", "sess-good"])
    assert result.exit_code == 0
    assert "Session Detail" in result.output
    assert "Prompt Quality" in result.output
    assert "Efficiency" in result.output


def test_sessions_detail_prefix_match(tmp_path, monkeypatch):
    """sessions --detail with prefix matches session ID."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--detail", "sess-g"])
    assert result.exit_code == 0
    assert "sess-good" in result.output


def test_sessions_detail_not_found(tmp_path, monkeypatch):
    """sessions --detail with unknown ID shows error."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--detail", "nonexistent"])
    assert result.exit_code == 1


def test_sessions_detail_json(tmp_path, monkeypatch):
    """sessions --detail --json returns single session as JSON."""
    db_path = _create_db_with_quality(tmp_path)
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    result = runner.invoke(app, ["sessions", "--detail", "sess-good", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["session_id"] == "sess-good"
    assert data["quality_score"] == 78.5


def test_sessions_help():
    """sessions --help shows usage information."""
    result = runner.invoke(app, ["sessions", "--help"])
    assert result.exit_code == 0
    assert "quality" in result.output.lower() or "session" in result.output.lower()
