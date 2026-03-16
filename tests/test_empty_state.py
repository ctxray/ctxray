"""Tests for empty-state UX across commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from reprompt.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def _empty_db(tmp_path, monkeypatch):
    """Point Settings at a fresh (empty) DB path."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "empty.db"))


def test_report_empty_db_shows_guidance(tmp_path, monkeypatch, runner):
    """report on empty DB tells user to scan first."""
    _empty_db(tmp_path, monkeypatch)
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
    assert "reprompt scan" in result.output


def test_report_empty_db_no_crash(tmp_path, monkeypatch, runner):
    """report on empty DB doesn't crash."""
    _empty_db(tmp_path, monkeypatch)
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0


def test_digest_empty_db_shows_guidance(tmp_path, monkeypatch, runner):
    """digest on empty DB tells user to scan first."""
    _empty_db(tmp_path, monkeypatch)
    result = runner.invoke(app, ["digest"])
    assert result.exit_code == 0
    assert "reprompt scan" in result.output


def test_digest_quiet_empty_db_no_crash(tmp_path, monkeypatch, runner):
    """digest --quiet on empty DB outputs something reasonable."""
    _empty_db(tmp_path, monkeypatch)
    result = runner.invoke(app, ["digest", "--quiet"])
    assert result.exit_code == 0


def test_digest_json_empty_db_returns_valid_json(tmp_path, monkeypatch, runner):
    """digest --format json on empty DB returns valid JSON with hint."""
    import json

    _empty_db(tmp_path, monkeypatch)
    result = runner.invoke(app, ["digest", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["error"] == "no data"
    assert "reprompt scan" in data["hint"]


def test_scan_shows_next_steps_on_first_scan(tmp_path, monkeypatch, runner):
    """First scan shows next-step suggestions."""
    import json as _json

    _empty_db(tmp_path, monkeypatch)

    # Create a minimal session file
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    f = session_dir / "test.jsonl"
    entries = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Implement the user authentication endpoint with JWT tokens",
                    }
                ],
            },
            "timestamp": "2026-03-10T10:00:00.000Z",
        },
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]},
            "timestamp": "2026-03-10T10:01:00.000Z",
        },
    ]
    f.write_text("\n".join(_json.dumps(e) for e in entries))

    result = runner.invoke(
        app, ["scan", "--quiet", "--source", "claude-code", "--path", str(session_dir)]
    )
    assert result.exit_code == 0
    # Should show next-step suggestions
    assert (
        "Try next" in result.output
        or "reprompt score" in result.output
        or "reprompt library" in result.output
    )
