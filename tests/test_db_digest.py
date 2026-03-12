"""Tests for digest_log DB methods."""

from __future__ import annotations

import pytest

from reprompt.storage.db import PromptDB


@pytest.fixture
def db(tmp_path):
    return PromptDB(tmp_path / "test.db")


class TestDigestLog:
    def test_digest_log_table_exists(self, db):
        """digest_log table is created by _init_schema."""
        import sqlite3

        conn = sqlite3.connect(str(db.path))
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        conn.close()
        assert "digest_log" in tables

    def test_log_digest_inserts_row(self, db):
        """log_digest() inserts a row into digest_log."""
        db.log_digest(
            period="7d",
            window_start="2026-03-03T00:00:00+00:00",
            window_end="2026-03-10T00:00:00+00:00",
            summary="reprompt: 42 prompts (+5), specificity 0.62 (↑)",
        )
        result = db.get_last_digest("7d")
        assert result is not None
        assert result["period"] == "7d"
        assert result["summary"] == "reprompt: 42 prompts (+5), specificity 0.62 (↑)"

    def test_get_last_digest_returns_none_when_empty(self, db):
        """get_last_digest() returns None when no entries exist."""
        result = db.get_last_digest("7d")
        assert result is None

    def test_get_last_digest_returns_most_recent(self, db):
        """get_last_digest() returns the newest row when multiple exist."""
        db.log_digest("7d", "2026-03-03T00:00:00+00:00", "2026-03-10T00:00:00+00:00", "old")
        db.log_digest("7d", "2026-03-10T00:00:00+00:00", "2026-03-17T00:00:00+00:00", "new")
        result = db.get_last_digest("7d")
        assert result is not None
        assert result["summary"] == "new"

    def test_log_digest_different_periods(self, db):
        """Different periods are stored and retrieved independently."""
        db.log_digest("7d", "2026-03-03T00:00:00+00:00", "2026-03-10T00:00:00+00:00", "weekly")
        db.log_digest("30d", "2026-02-08T00:00:00+00:00", "2026-03-10T00:00:00+00:00", "monthly")
        assert db.get_last_digest("7d")["summary"] == "weekly"
        assert db.get_last_digest("30d")["summary"] == "monthly"
