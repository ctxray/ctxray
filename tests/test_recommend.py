"""Tests for reprompt recommend command and engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.core.recommend import SPECIFICITY_UPGRADES, compute_recommendations
from reprompt.storage.db import PromptDB

runner = CliRunner()


def _make_db_with_data(tmp: Path) -> PromptDB:
    """Create a DB with prompts and session meta for testing."""
    db = PromptDB(tmp / "test.db")

    # Insert some prompts with sessions
    for i, (text, eff) in enumerate(
        [
            ("Fix the bug", 0.2),
            ("Fix test", 0.15),
            ("Add unit tests for the user registration endpoint", 0.8),
            ("Implement rate limiting middleware for the API endpoints", 0.9),
            ("Refactor the database connection to use connection pooling", 0.7),
            ("debug", 0.1),
            ("Explain how the caching middleware works in detail", 0.6),
        ]
    ):
        session_id = f"session-{i}"
        db.insert_prompt(
            text,
            source="claude-code",
            project="test-project",
            session_id=session_id,
            timestamp=f"2026-01-{10 + i:02d}T10:00:00Z",
        )
        db.upsert_session_meta(
            session_id=session_id,
            source="claude-code",
            project="test-project",
            start_time=f"2026-01-{10 + i:02d}T10:00:00Z",
            end_time=f"2026-01-{10 + i:02d}T11:00:00Z",
            duration_seconds=3600,
            prompt_count=1,
            tool_call_count=5,
            error_count=1 if eff < 0.3 else 0,
            final_status="success" if eff >= 0.5 else "error",
            avg_prompt_length=len(text),
            effectiveness_score=eff,
        )
    return db


class TestComputeRecommendations:
    def test_returns_expected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db_with_data(Path(tmp))
            result = compute_recommendations(db)
            assert "best_prompts" in result
            assert "short_prompt_alerts" in result
            assert "category_tips" in result
            assert "specificity_tips" in result
            assert "category_effectiveness" in result
            assert "overall_tips" in result
            assert "total_prompts" in result

    def test_best_prompts_high_effectiveness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db_with_data(Path(tmp))
            result = compute_recommendations(db)
            best = result["best_prompts"]
            assert len(best) > 0
            for p in best:
                assert p["effectiveness"] >= 0.6

    def test_short_prompt_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db_with_data(Path(tmp))
            result = compute_recommendations(db)
            alerts = result["short_prompt_alerts"]
            for a in alerts:
                assert a["char_count"] < 40

    def test_category_effectiveness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db_with_data(Path(tmp))
            result = compute_recommendations(db)
            cat_eff = result["category_effectiveness"]
            assert isinstance(cat_eff, dict)
            for cat, score in cat_eff.items():
                assert 0 <= score <= 1

    def test_empty_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = PromptDB(Path(tmp) / "empty.db")
            result = compute_recommendations(db)
            assert result["total_prompts"] == 0
            assert result["best_prompts"] == []

    def test_total_prompts_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db_with_data(Path(tmp))
            result = compute_recommendations(db)
            assert result["total_prompts"] == 7


class TestSpecificityUpgrades:
    def test_all_categories_have_tips(self) -> None:
        expected = {"fix", "debug", "test", "refactor", "implement"}
        assert set(SPECIFICITY_UPGRADES.keys()) == expected

    def test_tips_are_nonempty(self) -> None:
        for cat, tip in SPECIFICITY_UPGRADES.items():
            assert len(tip) > 20, f"Tip for {cat} is too short"


class TestRecommendCommand:
    def test_recommend_runs(self) -> None:
        result = runner.invoke(app, ["recommend"])
        assert result.exit_code == 0

    def test_recommend_json(self) -> None:
        result = runner.invoke(app, ["recommend", "--format", "json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "best_prompts" in data

    def test_recommend_shows_header(self) -> None:
        result = runner.invoke(app, ["recommend"])
        assert result.exit_code == 0
        assert "recommend" in result.output.lower() or "Prompt" in result.output


def test_best_by_category(tmp_path):
    """Recommendations include best prompts grouped by category."""
    from reprompt.core.recommend import compute_recommendations
    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    # Insert prompts with session meta for effectiveness
    db.insert_prompt(
        "Fix auth bug in login.py — returns 401 for valid tokens",
        source="test",
        project="p",
        session_id="s1",
        timestamp="2026-03-01",
    )
    db.insert_prompt(
        "Add comprehensive unit tests for UserService.create_user",
        source="test",
        project="p",
        session_id="s1",
        timestamp="2026-03-01",
    )
    db.upsert_session_meta(
        session_id="s1",
        source="test",
        project="p",
        start_time="2026-03-01T10:00:00",
        end_time="2026-03-01T11:00:00",
        duration_seconds=3600,
        prompt_count=2,
        tool_call_count=10,
        error_count=0,
        final_status="success",
        avg_prompt_length=50.0,
        effectiveness_score=0.8,
    )
    result = compute_recommendations(db)
    assert "best_by_category" in result
    # Should have at least one category with best prompts
    if result["best_by_category"]:
        first_cat = list(result["best_by_category"].values())[0]
        assert "text" in first_cat
        assert "effectiveness" in first_cat


def test_progress_tracking(tmp_path):
    """Recommendations include progress data when enough history exists."""
    from reprompt.core.recommend import compute_recommendations
    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    # Insert prompts across two time periods
    for i in range(5):
        db.insert_prompt(
            f"Short prompt {i}",
            source="test",
            project="p",
            session_id=f"old-{i}",
            timestamp=f"2026-02-0{i + 1}",
        )
    for i in range(5):
        db.insert_prompt(
            f"Detailed prompt with specific file reference and constraints number {i}",
            source="test",
            project="p",
            session_id=f"new-{i}",
            timestamp=f"2026-03-0{i + 1}",
        )

    result = compute_recommendations(db)
    assert "progress" in result
    assert result["progress"] != {}
    assert "older_avg_length" in result["progress"]
    assert "newer_avg_length" in result["progress"]
