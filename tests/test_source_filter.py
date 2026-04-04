"""Tests for --source filter consistency across commands."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from ctxray.core.digest import build_digest
from ctxray.core.trends import compute_trends
from ctxray.storage.db import PromptDB


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (Rich color output on CI)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.fixture
def db(tmp_path):
    return PromptDB(tmp_path / "test.db")


def _seed_two_sources(db: PromptDB) -> None:
    """Insert prompts from two different sources for filter testing."""
    now = datetime.now(timezone.utc)
    for i in range(5):
        ts = (now - timedelta(days=1, hours=i)).isoformat()
        db.insert_prompt(
            f"claude prompt {i} with specific implementation details for auth",
            source="claude-code",
            timestamp=ts,
        )
    for i in range(3):
        ts = (now - timedelta(days=1, hours=i + 5)).isoformat()
        db.insert_prompt(
            f"cursor prompt {i} with unique debugging context for errors",
            source="cursor",
            timestamp=ts,
        )


def _store_all_features(db: PromptDB) -> None:
    """Extract and store features for all prompts in db."""
    from dataclasses import asdict

    from ctxray.core.extractors import extract_features
    from ctxray.core.scorer import score_prompt

    for p in db.get_all_prompts():
        dna = extract_features(p["text"], source=p["source"], session_id="test")
        breakdown = score_prompt(dna)
        dna.overall_score = breakdown.total
        db.store_features(p["hash"], asdict(dna))


class TestGetAllFeaturesSource:
    def test_unfiltered_returns_all(self, db):
        _seed_two_sources(db)
        _store_all_features(db)
        all_features = db.get_all_features()
        assert len(all_features) == 8

    def test_filtered_returns_subset(self, db):
        _seed_two_sources(db)
        _store_all_features(db)
        claude_features = db.get_all_features(source="claude-code")
        cursor_features = db.get_all_features(source="cursor")
        assert len(claude_features) == 5
        assert len(cursor_features) == 3

    def test_nonexistent_source_returns_empty(self, db):
        _seed_two_sources(db)
        assert db.get_all_features(source="nonexistent") == []


class TestGetAllPromptsSource:
    def test_filter_by_source(self, db):
        _seed_two_sources(db)
        claude = db.get_all_prompts(source="claude-code")
        cursor = db.get_all_prompts(source="cursor")
        all_prompts = db.get_all_prompts()
        assert len(claude) == 5
        assert len(cursor) == 3
        assert len(all_prompts) == 8


class TestGetPromptsInRangeSource:
    def test_filter_by_source(self, db):
        _seed_two_sources(db)
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=7)).isoformat()
        end = (now + timedelta(days=1)).isoformat()

        all_in_range = db.get_prompts_in_range(start, end)
        claude_in_range = db.get_prompts_in_range(start, end, source="claude-code")
        cursor_in_range = db.get_prompts_in_range(start, end, source="cursor")

        assert len(all_in_range) == 8
        assert len(claude_in_range) == 5
        assert len(cursor_in_range) == 3


class TestDigestSourceFilter:
    def test_source_filtered_skips_log_digest(self, db):
        _seed_two_sources(db)
        # Unfiltered run logs
        build_digest(db, period="7d")
        history_before = db.get_digest_history(period="7d", limit=10)

        # Source-filtered run should NOT add log entry
        count_before = len(history_before)
        build_digest(db, period="7d", source="claude-code")
        history_after = db.get_digest_history(period="7d", limit=10)
        assert len(history_after) == count_before

    def test_source_filtered_returns_subset_counts(self, db):
        _seed_two_sources(db)
        full = build_digest(db, period="7d")
        filtered = build_digest(db, period="7d", source="claude-code")

        # Filtered should have fewer or equal prompts
        assert filtered["current"]["prompt_count"] <= full["current"]["prompt_count"]


class TestTrendsSourceFilter:
    def test_source_filter_threads_through(self, db):
        _seed_two_sources(db)
        full = compute_trends(db, period="7d", n_windows=2)
        filtered = compute_trends(db, period="7d", n_windows=2, source="cursor")

        # At least one window should differ in count
        full_total = sum(w["prompt_count"] for w in full["windows"])
        filtered_total = sum(w["prompt_count"] for w in filtered["windows"])
        assert filtered_total <= full_total


class TestCLISourceFlag:
    """Verify --source flag is registered on the 4 newly added commands."""

    def test_insights_has_source_flag(self):
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["insights", "--help"])
        assert "--source" in _strip_ansi(result.output)

    def test_trends_has_source_flag(self):
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["trends", "--help"])
        assert "--source" in _strip_ansi(result.output)

    def test_digest_has_source_flag(self):
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["digest", "--help"])
        assert "--source" in _strip_ansi(result.output)

    def test_style_has_source_flag(self):
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["style", "--help"])
        assert "--source" in _strip_ansi(result.output)
