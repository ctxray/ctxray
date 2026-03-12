"""Unit tests for build_digest()."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from reprompt.core.digest import build_digest
from reprompt.storage.db import PromptDB


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
        _insert_prompts(db, count=5, days_ago=3)   # current window (last 7d)
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
        _insert_prompts(db, count=2, days_ago=3)   # current window (last 7d)
        _insert_prompts(db, count=5, days_ago=10)  # previous window (7-14d ago)
        result = build_digest(db, period="7d")
        assert result["count_delta"] == -3  # 2 - 5

    def test_spec_delta_sign(self, db):
        """spec_delta is positive when current specificity > previous."""
        _insert_prompts(db, count=10, days_ago=3)
        result = build_digest(db, period="7d")
        # With 0 prompts in previous window, delta should be >= 0
        assert result["spec_delta"] >= 0
