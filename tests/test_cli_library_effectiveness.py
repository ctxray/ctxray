"""Tests for library command effectiveness column."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from reprompt.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def _setup_db_with_effectiveness(tmp_path, monkeypatch):
    """Helper: create a DB with patterns that have effectiveness data."""
    from reprompt.storage.db import PromptDB

    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    db = PromptDB(tmp_path / "test.db")

    db.insert_prompt(
        "Fix the failing tests in the CI pipeline", source="claude-code", session_id="s1"
    )
    db.update_prompt_effectiveness("s1", 0.82)

    db.upsert_pattern(
        pattern_text="Fix the failing tests",
        frequency=3,
        avg_length=55.0,
        projects=[],
        category="debug",
        first_seen="2026-03-10",
        last_seen="2026-03-10",
        examples=[],
    )
    db.compute_pattern_effectiveness()
    return db


def test_library_shows_effectiveness_column_when_data_exists(tmp_path, monkeypatch, runner):
    """library command shows Eff column when effectiveness data is available."""
    _setup_db_with_effectiveness(tmp_path, monkeypatch)
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0
    assert "Eff" in result.output


def test_library_shows_effectiveness_score(tmp_path, monkeypatch, runner):
    """library command shows the effectiveness score for patterns with data."""
    _setup_db_with_effectiveness(tmp_path, monkeypatch)
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0
    assert "0.8" in result.output or "★" in result.output


def test_library_no_crash_without_effectiveness_data(tmp_path, monkeypatch, runner):
    """library command works fine when no effectiveness data exists."""
    from reprompt.storage.db import PromptDB

    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    db = PromptDB(tmp_path / "test.db")
    db.upsert_pattern(
        pattern_text="Write unit tests for",
        frequency=2,
        avg_length=30.0,
        projects=[],
        category="testing",
        first_seen="2026-03-10",
        last_seen="2026-03-10",
        examples=[],
    )
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0
    assert "Write unit tests for" in result.output


def test_library_no_patterns_message(tmp_path, monkeypatch, runner):
    """library command shows guidance message when no patterns exist."""
    from reprompt.storage.db import PromptDB

    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    PromptDB(tmp_path / "test.db")
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0
    assert "reprompt scan" in result.output
