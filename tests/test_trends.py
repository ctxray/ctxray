"""Tests for prompt evolution tracking."""

from __future__ import annotations

from datetime import datetime, timezone

from reprompt.core.timeutil import TimeWindow
from reprompt.core.trends import (
    _compute_specificity,
    _norm,
    compute_trends,
    compute_window_snapshot,
    generate_insights,
)
from reprompt.storage.db import PromptDB


def _populate_db(db: PromptDB, count: int = 10, start_date: str = "2026-03-05") -> None:
    """Insert test prompts with varied content."""
    prompts = [
        "fix the authentication bug in the login handler module",
        "add comprehensive unit tests for the payment processing service",
        "refactor the database connection pool to use async patterns",
        "implement the new search feature with full-text indexing support",
        "debug the kubernetes deployment failing on staging environment",
        "review the pull request for the user settings API endpoint",
        "explain how the middleware authentication chain works in detail",
        "configure the CI pipeline to run integration tests in parallel",
        "update the README with the new installation instructions guide",
        "optimize the query performance for the analytics dashboard page",
    ]
    for i in range(min(count, len(prompts))):
        h = i % 24
        db.insert_prompt(
            prompts[i],
            source="claude-code",
            timestamp=f"{start_date}T{h:02d}:00:00Z",
        )


class TestNorm:
    def test_within_range(self):
        assert _norm(275, 50, 500) == 0.5

    def test_below_lo(self):
        assert _norm(10, 50, 500) == 0.0

    def test_above_hi(self):
        assert _norm(600, 50, 500) == 1.0

    def test_equal_bounds(self):
        assert _norm(50, 50, 50) == 0.0


class TestComputeSpecificity:
    def test_returns_between_0_and_1(self):
        score = _compute_specificity(150, 80, {"debug": 5, "implement": 10, "test": 3})
        assert 0.0 <= score <= 1.0

    def test_empty_categories(self):
        score = _compute_specificity(100, 50, {})
        assert score >= 0.0

    def test_higher_diversity_higher_score(self):
        low = _compute_specificity(150, 80, {"debug": 20})
        high = _compute_specificity(150, 80, {"debug": 5, "implement": 5, "test": 5, "review": 5})
        assert high > low


class TestComputeWindowSnapshot:
    def test_empty_window(self, tmp_path):
        db = PromptDB(tmp_path / "test.db")
        window = TimeWindow(
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 8, tzinfo=timezone.utc),
            label="Jan 01 - Jan 08",
        )
        snap = compute_window_snapshot(db, window, "7d")
        assert snap["prompt_count"] == 0
        assert snap["specificity_score"] == 0.0

    def test_populated_window(self, tmp_path):
        db = PromptDB(tmp_path / "test.db")
        _populate_db(db, 5, start_date="2026-03-05")
        window = TimeWindow(
            start=datetime(2026, 3, 4, tzinfo=timezone.utc),
            end=datetime(2026, 3, 8, tzinfo=timezone.utc),
            label="Mar 04 - Mar 08",
        )
        snap = compute_window_snapshot(db, window, "7d")
        assert snap["prompt_count"] == 5
        assert snap["avg_length"] > 0
        assert snap["vocab_size"] > 0
        assert 0.0 <= snap["specificity_score"] <= 1.0

    def test_snapshot_stored_in_db(self, tmp_path):
        db = PromptDB(tmp_path / "test.db")
        _populate_db(db, 3, start_date="2026-03-05")
        window = TimeWindow(
            start=datetime(2026, 3, 4, tzinfo=timezone.utc),
            end=datetime(2026, 3, 8, tzinfo=timezone.utc),
            label="Mar 04 - Mar 08",
        )
        compute_window_snapshot(db, window, "7d")
        stored = db.get_snapshots("7d")
        assert len(stored) == 1
        assert stored[0]["prompt_count"] == 3


class TestComputeTrends:
    def test_empty_db(self, tmp_path):
        db = PromptDB(tmp_path / "test.db")
        result = compute_trends(db, period="7d", n_windows=4)
        assert len(result["windows"]) == 4
        assert all(w["prompt_count"] == 0 for w in result["windows"])

    def test_with_data(self, tmp_path):
        db = PromptDB(tmp_path / "test.db")
        # Insert prompts spread across recent weeks
        anchor = datetime.now(timezone.utc)
        for day_offset in range(0, 21, 3):
            ts = (anchor - __import__("datetime").timedelta(days=day_offset)).isoformat()
            db.insert_prompt(
                f"unique prompt about topic number {day_offset} with enough detail",
                source="cc",
                timestamp=ts,
            )
        result = compute_trends(db, period="7d", n_windows=4)
        assert "windows" in result
        assert "insights" in result
        assert len(result["windows"]) == 4

    def test_returns_period(self, tmp_path):
        db = PromptDB(tmp_path / "test.db")
        result = compute_trends(db, period="30d", n_windows=2)
        assert result["period"] == "30d"


class TestGenerateInsights:
    def test_no_data(self):
        snapshots = [{"prompt_count": 0, "specificity_score": 0.0}]
        insights = generate_insights(snapshots)
        assert any("No prompt data" in i or "1 period" in i for i in insights)

    def test_improving_specificity(self):
        snapshots = [
            {
                "prompt_count": 10,
                "specificity_score": 0.3,
                "category_distribution": {"debug": 10},
            },
            {
                "prompt_count": 15,
                "specificity_score": 0.6,
                "category_distribution": {"debug": 5, "implement": 10},
            },
        ]
        insights = generate_insights(snapshots)
        assert any("more specific" in i for i in insights)

    def test_declining_specificity(self):
        snapshots = [
            {
                "prompt_count": 10,
                "specificity_score": 0.7,
                "category_distribution": {},
            },
            {
                "prompt_count": 8,
                "specificity_score": 0.3,
                "category_distribution": {},
            },
        ]
        insights = generate_insights(snapshots)
        assert any("decreased" in i for i in insights)

    def test_activity_change(self):
        snapshots = [
            {"prompt_count": 10, "specificity_score": 0.5, "category_distribution": {}},
            {"prompt_count": 20, "specificity_score": 0.5, "category_distribution": {}},
        ]
        insights = generate_insights(snapshots)
        assert any("up" in i.lower() for i in insights)
