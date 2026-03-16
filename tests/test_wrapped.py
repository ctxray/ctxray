"""Tests for Wrapped aggregate DB queries."""

from __future__ import annotations

import hashlib

import pytest

from reprompt.core.wrapped import WrappedReport, build_wrapped
from reprompt.storage.db import PromptDB


def _hash(text: str) -> str:
    """Mirror PromptDB._hash for test data."""
    return hashlib.sha256(text.strip().encode()).hexdigest()


def _make_features(
    *,
    structure: float = 15.0,
    context: float = 15.0,
    position: float = 12.0,
    repetition: float = 8.0,
    clarity: float = 10.0,
    overall_score: float = 60.0,
    task_type: str = "code_generation",
) -> dict:
    """Build a minimal features dict matching scorer output shape."""
    return {
        "structure": structure,
        "context": context,
        "position": position,
        "repetition": repetition,
        "clarity": clarity,
        "overall_score": overall_score,
        "task_type": task_type,
    }


@pytest.fixture()
def db(tmp_path):
    """Fresh DB per test."""
    return PromptDB(tmp_path / "test.db")


@pytest.fixture()
def populated_db(db):
    """DB with 10 prompts, 5 of which have features scored."""
    prompts = [f"Prompt number {i}: do something useful" for i in range(10)]
    for p in prompts:
        db.insert_prompt(p, source="test", project="proj")

    scored_data = [
        _make_features(
            structure=20.0,
            context=18.0,
            position=16.0,
            repetition=12.0,
            clarity=14.0,
            overall_score=80.0,
            task_type="code_generation",
        ),
        _make_features(
            structure=10.0,
            context=12.0,
            position=8.0,
            repetition=6.0,
            clarity=4.0,
            overall_score=40.0,
            task_type="debugging",
        ),
        _make_features(
            structure=25.0,
            context=25.0,
            position=20.0,
            repetition=15.0,
            clarity=15.0,
            overall_score=100.0,
            task_type="code_generation",
        ),
        _make_features(
            structure=15.0,
            context=15.0,
            position=12.0,
            repetition=8.0,
            clarity=10.0,
            overall_score=60.0,
            task_type="refactoring",
        ),
        _make_features(
            structure=5.0,
            context=5.0,
            position=4.0,
            repetition=2.0,
            clarity=2.0,
            overall_score=18.0,
            task_type="debugging",
        ),
    ]
    for i, features in enumerate(scored_data):
        prompt_hash = _hash(prompts[i])
        db.store_features(prompt_hash, features)

    return db


# ---- get_wrapped_stats ------------------------------------------------


class TestGetWrappedStats:
    def test_returns_dict(self, populated_db):
        """Result is a dict with expected top-level keys."""
        stats = populated_db.get_wrapped_stats()
        assert isinstance(stats, dict)
        expected_keys = {
            "total_prompts",
            "scored_prompts",
            "avg_scores",
            "avg_overall",
            "top_score",
            "top_task_type",
        }
        assert expected_keys == set(stats.keys())

    def test_total_prompts(self, populated_db):
        """total_prompts counts all rows in prompts table."""
        stats = populated_db.get_wrapped_stats()
        assert stats["total_prompts"] == 10

    def test_scored_prompts(self, populated_db):
        """scored_prompts counts rows in prompt_features."""
        stats = populated_db.get_wrapped_stats()
        assert stats["scored_prompts"] == 5

    def test_avg_scores_keys(self, populated_db):
        """avg_scores has all five category keys."""
        stats = populated_db.get_wrapped_stats()
        assert set(stats["avg_scores"].keys()) == {
            "structure",
            "context",
            "position",
            "repetition",
            "clarity",
        }

    def test_avg_scores_values(self, populated_db):
        """avg_scores are arithmetic means of the category scores."""
        stats = populated_db.get_wrapped_stats()
        avg = stats["avg_scores"]
        # (20+10+25+15+5)/5 = 15.0
        assert avg["structure"] == pytest.approx(15.0)
        # (18+12+25+15+5)/5 = 15.0
        assert avg["context"] == pytest.approx(15.0)
        # (16+8+20+12+4)/5 = 12.0
        assert avg["position"] == pytest.approx(12.0)
        # (12+6+15+8+2)/5 = 8.6
        assert avg["repetition"] == pytest.approx(8.6)
        # (14+4+15+10+2)/5 = 9.0
        assert avg["clarity"] == pytest.approx(9.0)

    def test_avg_overall(self, populated_db):
        """avg_overall is the mean of overall_score across scored prompts."""
        stats = populated_db.get_wrapped_stats()
        # (80+40+100+60+18)/5 = 59.6
        assert stats["avg_overall"] == pytest.approx(59.6)

    def test_top_score(self, populated_db):
        """top_score is the max overall_score."""
        stats = populated_db.get_wrapped_stats()
        assert stats["top_score"] == pytest.approx(100.0)

    def test_top_task_type(self, populated_db):
        """top_task_type is the most common task_type."""
        stats = populated_db.get_wrapped_stats()
        # code_generation=2, debugging=2, refactoring=1 -> tie broken arbitrarily
        # but code_generation and debugging both have 2; accept either
        assert stats["top_task_type"] in ("code_generation", "debugging")

    def test_empty_db(self, db):
        """All zeros when no data exists."""
        stats = db.get_wrapped_stats()
        assert stats["total_prompts"] == 0
        assert stats["scored_prompts"] == 0
        assert stats["avg_overall"] == 0.0
        assert stats["top_score"] == 0.0
        assert stats["top_task_type"] is None
        for v in stats["avg_scores"].values():
            assert v == 0.0


# ---- get_task_type_distribution ----------------------------------------


class TestGetTaskTypeDistribution:
    def test_returns_dict(self, populated_db):
        """Result is a dict mapping task_type -> count."""
        dist = populated_db.get_task_type_distribution()
        assert isinstance(dist, dict)

    def test_counts(self, populated_db):
        """Counts match inserted data."""
        dist = populated_db.get_task_type_distribution()
        assert dist["code_generation"] == 2
        assert dist["debugging"] == 2
        assert dist["refactoring"] == 1

    def test_sorted_by_count_desc(self, populated_db):
        """Keys are ordered by count descending."""
        dist = populated_db.get_task_type_distribution()
        counts = list(dist.values())
        assert counts == sorted(counts, reverse=True)

    def test_empty_db(self, db):
        """Empty dict when no features stored."""
        dist = db.get_task_type_distribution()
        assert dist == {}


# ---- get_score_history -------------------------------------------------


class TestGetScoreHistory:
    def test_returns_list(self, populated_db):
        """Result is a list of dicts."""
        history = populated_db.get_score_history()
        assert isinstance(history, list)
        assert all(isinstance(item, dict) for item in history)

    def test_item_keys(self, populated_db):
        """Each item has the expected keys."""
        history = populated_db.get_score_history()
        expected_keys = {"prompt_hash", "overall_score", "task_type", "computed_at"}
        for item in history:
            assert expected_keys == set(item.keys())

    def test_count(self, populated_db):
        """Returns all 5 scored prompts (under default limit of 50)."""
        history = populated_db.get_score_history()
        assert len(history) == 5

    def test_limit(self, populated_db):
        """Respects the limit parameter."""
        history = populated_db.get_score_history(limit=2)
        assert len(history) == 2

    def test_ordered_by_computed_at_desc(self, populated_db):
        """Results are ordered by computed_at descending (newest first)."""
        history = populated_db.get_score_history()
        dates = [item["computed_at"] for item in history]
        assert dates == sorted(dates, reverse=True)

    def test_empty_db(self, db):
        """Empty list when no features stored."""
        history = db.get_score_history()
        assert history == []

    def test_excludes_null_scores(self, db):
        """Prompts with NULL overall_score are excluded."""
        db.insert_prompt("test prompt", source="test")
        h = _hash("test prompt")
        # Store features without overall_score (will be 0.0 from .get default)
        # But let's directly insert a row with NULL overall_score to test
        conn = db._conn()
        try:
            conn.execute(
                """INSERT INTO prompt_features
                   (prompt_hash, features_json, overall_score, task_type, computed_at)
                   VALUES (?, ?, NULL, 'other', datetime('now'))""",
                (h, "{}"),
            )
            conn.commit()
        finally:
            conn.close()
        history = db.get_score_history()
        assert history == []


# ---- build_wrapped / WrappedReport ----------------------------------------


class TestBuildWrapped:
    def test_build_wrapped_returns_report(self, populated_db):
        report = build_wrapped(populated_db)
        assert isinstance(report, WrappedReport)
        assert report.total_prompts >= 10
        assert report.persona is not None

    def test_build_wrapped_has_scores(self, populated_db):
        report = build_wrapped(populated_db)
        assert hasattr(report, "avg_scores")
        assert hasattr(report, "avg_overall")

    def test_build_wrapped_empty_db(self, tmp_path):
        d = PromptDB(tmp_path / "empty.db")
        report = build_wrapped(d)
        assert report.total_prompts == 0
        assert report.persona is not None  # should default to explorer

    def test_report_to_dict(self, populated_db):
        report = build_wrapped(populated_db)
        d = report.to_dict()
        assert "persona" in d
        assert "avg_scores" in d
        assert "name" in d["persona"]
