"""Tests for DB time-range queries and snapshot storage."""

from __future__ import annotations

from ctxray.storage.db import PromptDB


def test_get_prompts_in_range(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("early prompt about auth", source="cc", timestamp="2026-03-01T10:00:00Z")
    db.insert_prompt("mid prompt about tests", source="cc", timestamp="2026-03-05T10:00:00Z")
    db.insert_prompt("late prompt about deploy", source="cc", timestamp="2026-03-10T10:00:00Z")

    results = db.get_prompts_in_range("2026-03-04T00:00:00Z", "2026-03-08T00:00:00Z")
    assert len(results) == 1
    assert "tests" in results[0]["text"]


def test_get_prompts_in_range_empty(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    results = db.get_prompts_in_range("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
    assert results == []


def test_get_prompts_in_range_excludes_dupes(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("original prompt here", source="cc", timestamp="2026-03-05T10:00:00Z")
    db.insert_prompt("duplicate prompt text", source="cc", timestamp="2026-03-05T11:00:00Z")
    # Mark second as duplicate
    db.mark_duplicate(2, 1)

    results = db.get_prompts_in_range(
        "2026-03-04T00:00:00Z", "2026-03-06T00:00:00Z", unique_only=True
    )
    assert len(results) == 1

    results_all = db.get_prompts_in_range(
        "2026-03-04T00:00:00Z", "2026-03-06T00:00:00Z", unique_only=False
    )
    assert len(results_all) == 2


def test_upsert_snapshot(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    snapshot = {
        "window_start": "2026-03-03T00:00:00Z",
        "window_end": "2026-03-10T00:00:00Z",
        "window_label": "Mar 03 - Mar 10",
        "period": "7d",
        "prompt_count": 42,
        "unique_count": 38,
        "avg_length": 127.5,
        "median_length": 110.0,
        "vocab_size": 89,
        "specificity_score": 0.64,
        "category_distribution": {"debug": 10, "implement": 15},
        "top_terms": [{"term": "unit tests", "tfidf": 0.45}],
        "computed_at": "2026-03-11T10:00:00Z",
    }
    db.upsert_snapshot(snapshot)

    rows = db.get_snapshots("7d")
    assert len(rows) == 1
    assert rows[0]["prompt_count"] == 42
    assert rows[0]["category_distribution"] == {"debug": 10, "implement": 15}
    assert rows[0]["top_terms"][0]["term"] == "unit tests"


def test_upsert_snapshot_updates_existing(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    base = {
        "window_start": "2026-03-03T00:00:00Z",
        "window_end": "2026-03-10T00:00:00Z",
        "period": "7d",
        "prompt_count": 42,
        "unique_count": 38,
        "computed_at": "2026-03-11T10:00:00Z",
    }
    db.upsert_snapshot(base)

    updated = {**base, "prompt_count": 50, "unique_count": 45}
    db.upsert_snapshot(updated)

    rows = db.get_snapshots("7d")
    assert len(rows) == 1
    assert rows[0]["prompt_count"] == 50


def test_get_snapshots_chronological(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    for i, start in enumerate(["2026-03-01", "2026-03-08", "2026-03-15"]):
        db.upsert_snapshot(
            {
                "window_start": f"{start}T00:00:00Z",
                "window_end": f"{start}T00:00:00Z",
                "period": "7d",
                "prompt_count": (i + 1) * 10,
                "unique_count": (i + 1) * 8,
                "computed_at": "2026-03-11T10:00:00Z",
            }
        )

    rows = db.get_snapshots("7d", limit=10)
    assert len(rows) == 3
    # Should be chronological (oldest first)
    assert rows[0]["prompt_count"] == 10
    assert rows[2]["prompt_count"] == 30


def test_get_snapshots_filters_by_period(tmp_path):
    db = PromptDB(tmp_path / "test.db")
    db.upsert_snapshot(
        {
            "window_start": "2026-03-01T00:00:00Z",
            "window_end": "2026-03-08T00:00:00Z",
            "period": "7d",
            "prompt_count": 42,
            "unique_count": 38,
            "computed_at": "2026-03-11T10:00:00Z",
        }
    )
    db.upsert_snapshot(
        {
            "window_start": "2026-03-01T00:00:00Z",
            "window_end": "2026-03-31T00:00:00Z",
            "period": "30d",
            "prompt_count": 150,
            "unique_count": 120,
            "computed_at": "2026-03-11T10:00:00Z",
        }
    )

    weekly = db.get_snapshots("7d")
    assert len(weekly) == 1
    assert weekly[0]["prompt_count"] == 42

    monthly = db.get_snapshots("30d")
    assert len(monthly) == 1
    assert monthly[0]["prompt_count"] == 150
