"""Unit tests for build_digest()."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ctxray.core.digest import build_digest
from ctxray.storage.db import PromptDB


@pytest.fixture
def db(tmp_path):
    return PromptDB(tmp_path / "test.db")


def _insert_prompts(db: PromptDB, count: int, days_ago: int) -> None:
    """Insert `count` prompts timestamped `days_ago` days in the past.

    Uses days_ago as part of the text to ensure distinct hashes across batches.
    """
    now = datetime.now(timezone.utc)
    for i in range(count):
        ts = (now - timedelta(days=days_ago, hours=i)).isoformat()
        db.insert_prompt(
            f"implement feature {i} bucket {days_ago} with specific requirements for auth",
            source="claude-code",
            timestamp=ts,
        )


class TestBuildDigest:
    def test_returns_required_keys(self, db):
        """build_digest() returns all expected keys."""
        result = build_digest(db, period="7d")
        assert "period" in result
        assert "current" in result
        assert "previous" in result
        assert "count_delta" in result
        assert "spec_delta" in result
        assert "summary" in result

    def test_period_stored_in_result(self, db):
        result = build_digest(db, period="30d")
        assert result["period"] == "30d"

    def test_empty_db_returns_zero_counts(self, db):
        result = build_digest(db)
        assert result["current"]["prompt_count"] == 0
        assert result["previous"]["prompt_count"] == 0
        assert result["count_delta"] == 0

    def test_count_delta_positive_when_current_has_more(self, db):
        """count_delta > 0 when current period has more prompts than previous."""
        _insert_prompts(db, count=5, days_ago=3)  # current window (last 7d)
        _insert_prompts(db, count=2, days_ago=10)  # previous window (7-14d ago)
        result = build_digest(db, period="7d")
        assert result["count_delta"] == 3  # 5 - 2

    def test_summary_is_one_line(self, db):
        """summary contains no newlines (used for --quiet output)."""
        result = build_digest(db)
        assert "\n" not in result["summary"]

    def test_summary_contains_prompt_count(self, db):
        """summary mentions the prompt count."""
        _insert_prompts(db, count=7, days_ago=3)
        result = build_digest(db)
        assert "7" in result["summary"]

    def test_digest_is_logged_to_db(self, db):
        """build_digest() stores a row in digest_log."""
        build_digest(db, period="7d")
        logged = db.get_last_digest("7d")
        assert logged is not None
        assert logged["period"] == "7d"

    def test_count_delta_negative_when_previous_has_more(self, db):
        """count_delta < 0 when previous period has more prompts than current."""
        _insert_prompts(db, count=2, days_ago=3)  # current window (last 7d)
        _insert_prompts(db, count=5, days_ago=10)  # previous window (7-14d ago)
        result = build_digest(db, period="7d")
        assert result["count_delta"] == -3  # 2 - 5

    def test_spec_delta_sign(self, db):
        """spec_delta is positive when current specificity > previous."""
        _insert_prompts(db, count=10, days_ago=3)
        result = build_digest(db, period="7d")
        # With 0 prompts in previous window, delta should be >= 0
        assert result["spec_delta"] >= 0


# ---------------------------------------------------------------------------
# Effectiveness in digest
# ---------------------------------------------------------------------------


def _make_db_with_session_meta(tmp_path):
    """Helper: DB with session metadata for effectiveness testing."""
    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.upsert_session_meta(
        session_id="s1",
        source="claude-code",
        project="myproject",
        start_time="2026-03-10T10:00:00+00:00",
        end_time="2026-03-10T11:00:00+00:00",
        duration_seconds=3600,
        prompt_count=5,
        tool_call_count=10,
        error_count=0,
        final_status="success",
        avg_prompt_length=120.0,
        effectiveness_score=0.78,
    )
    return db


def test_build_digest_includes_eff_avg(tmp_path):
    """build_digest returns eff_avg from session_meta data."""
    from unittest.mock import patch

    from ctxray.core.digest import build_digest

    db = _make_db_with_session_meta(tmp_path)

    with patch("ctxray.core.digest.compute_window_snapshot") as mock_snap:
        mock_snap.return_value = {
            "prompt_count": 5,
            "specificity_score": 0.60,
            "avg_length": 100.0,
            "category_distribution": {},
        }
        result = build_digest(db, period="7d")

    assert "eff_avg" in result
    assert result["eff_avg"] == pytest.approx(0.78, abs=0.01)


def test_build_digest_eff_avg_none_when_no_sessions(tmp_path):
    """build_digest returns eff_avg=None when no session data exists."""
    from unittest.mock import patch

    from ctxray.core.digest import build_digest
    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")

    with patch("ctxray.core.digest.compute_window_snapshot") as mock_snap:
        mock_snap.return_value = {
            "prompt_count": 0,
            "specificity_score": 0.0,
            "avg_length": 0.0,
            "category_distribution": {},
        }
        result = build_digest(db, period="7d")

    assert result["eff_avg"] is None


def test_render_digest_shows_effectiveness_when_present():
    """render_digest includes effectiveness line when eff_avg is provided."""
    from ctxray.output.terminal import render_digest

    snap = {"prompt_count": 10, "specificity_score": 0.65, "avg_length": 120.0}
    curr = {**snap, "category_distribution": {}}
    prev = {**snap, "prompt_count": 8, "avg_length": 110.0, "category_distribution": {}}
    data = {
        "period": "7d",
        "current": curr,
        "previous": prev,
        "count_delta": 2,
        "spec_delta": 0.05,
        "eff_avg": 0.78,
    }
    output = render_digest(data)
    assert "0.78" in output or "★" in output


def test_render_digest_no_crash_without_effectiveness():
    """render_digest works fine when eff_avg is absent or None."""
    from ctxray.output.terminal import render_digest

    snap = {"prompt_count": 10, "specificity_score": 0.65, "avg_length": 120.0}
    curr = {**snap, "category_distribution": {}}
    prev = {**snap, "prompt_count": 8, "avg_length": 110.0, "category_distribution": {}}
    data = {
        "period": "7d",
        "current": curr,
        "previous": prev,
        "count_delta": 2,
        "spec_delta": 0.05,
        "eff_avg": None,
    }
    output = render_digest(data)
    assert "Prompts this period" in output
