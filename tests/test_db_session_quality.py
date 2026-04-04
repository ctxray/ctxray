"""Tests for session quality DB migration and storage methods."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ctxray.storage.db import PromptDB


@pytest.fixture
def db(tmp_path: Path) -> PromptDB:
    return PromptDB(tmp_path / "test.db")


def _insert_session(db: PromptDB, session_id: str = "sess-1", source: str = "claude-code") -> None:
    """Insert a session_meta row so quality updates have a target."""
    db.upsert_session_meta(
        session_id=session_id,
        source=source,
        project="test-project",
        start_time="2026-03-28T10:00:00Z",
        end_time="2026-03-28T10:30:00Z",
        duration_seconds=1800,
        prompt_count=10,
        tool_call_count=20,
        error_count=2,
        final_status="success",
        avg_prompt_length=150.0,
        effectiveness_score=0.75,
    )


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestMigrationV3:
    def test_schema_version_is_3(self, db: PromptDB):
        conn = sqlite3.connect(str(db.path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        assert version == 3

    def test_quality_columns_exist(self, db: PromptDB):
        conn = sqlite3.connect(str(db.path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("PRAGMA table_info(session_meta)").fetchall()
        col_names = {r["name"] for r in row}
        conn.close()

        expected = {
            "quality_score",
            "prompt_quality_score",
            "efficiency_score",
            "focus_score",
            "outcome_score",
            "has_abandonment",
            "has_escalation",
            "stall_turns",
            "session_type",
            "quality_insight",
        }
        assert expected.issubset(col_names)

    def test_migration_idempotent(self, db: PromptDB):
        """Running migration again should not fail."""
        db._run_migrations()
        db._run_migrations()
        # No error = pass


# ---------------------------------------------------------------------------
# upsert_session_quality tests
# ---------------------------------------------------------------------------


class TestUpsertSessionQuality:
    def test_update_quality_on_existing_session(self, db: PromptDB):
        _insert_session(db, "sess-1")
        db.upsert_session_quality(
            session_id="sess-1",
            quality_score=72.5,
            prompt_quality_score=80.0,
            efficiency_score=65.0,
            focus_score=50.0,
            outcome_score=70.0,
            has_abandonment=False,
            has_escalation=True,
            stall_turns=3,
            session_type="debugging",
            quality_insight="Errors escalated through session",
        )
        sessions = db.get_sessions_with_quality(limit=10)
        assert len(sessions) == 1
        s = sessions[0]
        assert s["quality_score"] == 72.5
        assert s["prompt_quality_score"] == 80.0
        assert s["efficiency_score"] == 65.0
        assert s["focus_score"] == 50.0
        assert s["outcome_score"] == 70.0
        assert s["has_abandonment"] == 0
        assert s["has_escalation"] == 1
        assert s["stall_turns"] == 3
        assert s["session_type"] == "debugging"
        assert s["quality_insight"] == "Errors escalated through session"

    def test_update_nonexistent_session_no_error(self, db: PromptDB):
        """Updating quality for a missing session should silently do nothing."""
        db.upsert_session_quality(
            session_id="nonexistent",
            quality_score=50.0,
        )
        sessions = db.get_sessions_with_quality()
        assert len(sessions) == 0

    def test_partial_quality_null_components(self, db: PromptDB):
        _insert_session(db, "sess-1")
        db.upsert_session_quality(
            session_id="sess-1",
            quality_score=60.0,
            prompt_quality_score=60.0,
            # efficiency, focus, outcome left as None
        )
        sessions = db.get_sessions_with_quality()
        s = sessions[0]
        assert s["quality_score"] == 60.0
        assert s["prompt_quality_score"] == 60.0
        assert s["efficiency_score"] is None
        assert s["focus_score"] is None


# ---------------------------------------------------------------------------
# get_sessions_with_quality tests
# ---------------------------------------------------------------------------


class TestGetSessionsWithQuality:
    def test_empty_db_returns_empty(self, db: PromptDB):
        assert db.get_sessions_with_quality() == []

    def test_limit_respected(self, db: PromptDB):
        for i in range(5):
            _insert_session(db, f"sess-{i}")
        sessions = db.get_sessions_with_quality(limit=3)
        assert len(sessions) == 3

    def test_source_filter(self, db: PromptDB):
        _insert_session(db, "sess-cc", source="claude-code")
        _insert_session(db, "sess-cursor", source="cursor")
        sessions = db.get_sessions_with_quality(source="cursor")
        assert len(sessions) == 1
        assert sessions[0]["source"] == "cursor"

    def test_order_by_quality_score(self, db: PromptDB):
        _insert_session(db, "sess-low")
        _insert_session(db, "sess-high")
        db.upsert_session_quality(session_id="sess-low", quality_score=30.0)
        db.upsert_session_quality(session_id="sess-high", quality_score=90.0)
        sessions = db.get_sessions_with_quality(order_by="quality_score")
        assert sessions[0]["quality_score"] == 90.0
        assert sessions[1]["quality_score"] == 30.0

    def test_order_by_invalid_falls_back_to_start_time(self, db: PromptDB):
        _insert_session(db, "sess-1")
        # Should not raise even with invalid order_by
        sessions = db.get_sessions_with_quality(order_by="invalid_column")
        assert len(sessions) == 1

    def test_preserves_original_session_meta_fields(self, db: PromptDB):
        _insert_session(db, "sess-1")
        sessions = db.get_sessions_with_quality()
        s = sessions[0]
        # Original fields still accessible
        assert s["session_id"] == "sess-1"
        assert s["source"] == "claude-code"
        assert s["effectiveness_score"] == 0.75
        assert s["prompt_count"] == 10
