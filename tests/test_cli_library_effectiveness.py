"""Tests for library command (now deprecated)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ctxray.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def test_library_is_deprecated_and_shows_migration(tmp_path, monkeypatch, runner):
    """library command is deprecated and points to template list."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0
    assert "template list" in result.output


def test_library_exits_cleanly(tmp_path, monkeypatch, runner):
    """library command exits 0 regardless of DB content."""
    from ctxray.storage.db import PromptDB

    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
    db = PromptDB(tmp_path / "test.db")
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
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0
    # Should NOT render old table, just deprecation message
    assert "Prompt Library" not in result.output
    assert "template list" in result.output
