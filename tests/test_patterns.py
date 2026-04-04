"""Tests for personal prompt patterns analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctxray.core.patterns import analyze_patterns
from ctxray.storage.db import PromptDB


@pytest.fixture
def db(tmp_path: Path) -> PromptDB:
    return PromptDB(tmp_path / "test.db")


def _store_feature(db: PromptDB, text: str, task_type: str, **features: bool | float) -> None:
    """Store a prompt + features for pattern analysis."""
    import hashlib

    h = hashlib.sha256(text.encode()).hexdigest()

    conn = db._conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO prompts (hash, text, source, session_id) VALUES (?, ?, ?, ?)",
            (h, text, "test", "s1"),
        )
        feature_dict = {
            "has_error_messages": False,
            "has_file_references": False,
            "has_code_blocks": False,
            "has_constraints": False,
            "has_io_spec": False,
            "has_edge_cases": False,
            "has_examples": False,
            "has_output_format": False,
            "has_role_definition": False,
            "has_step_by_step": False,
            **features,
        }
        conn.execute(
            "INSERT OR REPLACE INTO prompt_features "
            "(prompt_hash, features_json, overall_score, task_type, computed_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (h, json.dumps(feature_dict), features.get("overall_score", 40.0), task_type),
        )
        conn.commit()
    finally:
        conn.close()


class TestAnalyzePatterns:
    def test_empty_db(self, db: PromptDB) -> None:
        report = analyze_patterns(db)
        assert report.total_analyzed == 0
        assert report.patterns == []
        assert report.top_gaps == []

    def test_single_task_type(self, db: PromptDB) -> None:
        for i in range(5):
            _store_feature(db, f"fix bug {i}", "debug")
        report = analyze_patterns(db)
        assert report.total_analyzed == 5
        assert "debug" in report.task_distribution

    def test_detects_missing_error_messages(self, db: PromptDB) -> None:
        # 4/5 debug prompts missing error messages
        for i in range(4):
            _store_feature(db, f"fix bug {i}", "debug", has_error_messages=False)
        _store_feature(db, "fix bug with error", "debug", has_error_messages=True)

        report = analyze_patterns(db)
        debug_pattern = next((p for p in report.patterns if p.task_type == "debug"), None)
        assert debug_pattern is not None
        error_gap = next((g for g in debug_pattern.gaps if g.feature == "has_error_messages"), None)
        assert error_gap is not None
        assert error_gap.missing_rate == 0.8  # 4/5

    def test_no_gap_when_feature_present(self, db: PromptDB) -> None:
        # All debug prompts have error messages
        for i in range(5):
            _store_feature(db, f"fix bug {i}", "debug", has_error_messages=True)

        report = analyze_patterns(db)
        debug_pattern = next((p for p in report.patterns if p.task_type == "debug"), None)
        if debug_pattern:
            error_gap = next(
                (g for g in debug_pattern.gaps if g.feature == "has_error_messages"), None
            )
            assert error_gap is None  # no gap reported

    def test_multiple_task_types(self, db: PromptDB) -> None:
        for i in range(5):
            _store_feature(db, f"fix bug {i}", "debug")
        for i in range(3):
            _store_feature(db, f"implement feature {i}", "implement")

        report = analyze_patterns(db)
        assert len(report.task_distribution) >= 2

    def test_top_gaps_deduplication(self, db: PromptDB) -> None:
        # file_references missing in both debug and implement
        for i in range(5):
            _store_feature(db, f"fix bug {i}", "debug", has_file_references=False)
        for i in range(5):
            _store_feature(db, f"implement feat {i}", "implement", has_file_references=False)

        report = analyze_patterns(db)
        file_gaps = [g for g in report.top_gaps if g.feature == "has_file_references"]
        assert len(file_gaps) == 1  # deduplicated

    def test_skips_small_task_groups(self, db: PromptDB) -> None:
        # Only 2 prompts — not enough for meaningful patterns
        _store_feature(db, "review code 1", "review")
        _store_feature(db, "review code 2", "review")

        report = analyze_patterns(db)
        review_pattern = next((p for p in report.patterns if p.task_type == "review"), None)
        assert review_pattern is None  # skipped, need >= 3

    def test_json_serializable(self, db: PromptDB) -> None:
        for i in range(5):
            _store_feature(db, f"fix bug {i}", "debug")

        from dataclasses import asdict

        report = analyze_patterns(db)
        data = asdict(report)
        json.dumps(data)  # should not raise

    def test_gap_has_suggestion(self, db: PromptDB) -> None:
        for i in range(5):
            _store_feature(db, f"fix bug {i}", "debug", has_error_messages=False)

        report = analyze_patterns(db)
        debug_pattern = next((p for p in report.patterns if p.task_type == "debug"), None)
        assert debug_pattern is not None
        for gap in debug_pattern.gaps:
            assert gap.suggestion  # non-empty
            assert gap.impact in ("high", "medium", "low")


class TestPatternsCLI:
    def test_patterns_command_exists(self) -> None:
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["patterns", "--help"])
        assert result.exit_code == 0
        assert "personal" in result.output.lower() or "weakness" in result.output.lower()

    def test_patterns_json_output(self) -> None:
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["patterns", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_analyzed" in data
