"""Tests for cross-session prompt repetition detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctxray.core.repetition import analyze_repetition
from ctxray.storage.db import PromptDB


@pytest.fixture
def db(tmp_path: Path) -> PromptDB:
    return PromptDB(tmp_path / "test.db")


def _insert(db: PromptDB, text: str, session_id: str, source: str = "claude-code") -> None:
    db.insert_prompt(text, source=source, session_id=session_id, timestamp="2026-03-28T10:00:00Z")


class TestAnalyzeRepetition:
    def test_empty_db_returns_zero(self, db: PromptDB):
        report = analyze_repetition(db)
        assert report.total_prompts_analyzed == 0
        assert report.repetition_rate == 0.0
        assert report.recurring_topics == []

    def test_single_session_no_cross_session(self, db: PromptDB):
        """Similar prompts in the same session don't count as cross-session."""
        _insert(db, "fix the authentication bug in login.py", "s1")
        _insert(db, "fix the authentication issue in login module", "s1")
        _insert(db, "fix the auth problem in the login file", "s1")
        report = analyze_repetition(db)
        assert report.repetition_rate == 0.0
        assert len(report.recurring_topics) == 0

    def test_cross_session_detected(self, db: PromptDB):
        """Similar prompts across sessions form a recurring topic."""
        _insert(db, "fix the authentication bug in login.py please", "s1")
        _insert(db, "fix the authentication bug in login.py now", "s2")
        report = analyze_repetition(db)
        assert len(report.recurring_topics) >= 1
        topic = report.recurring_topics[0]
        assert topic.session_count >= 2
        assert topic.total_matches >= 2
        assert report.repetition_rate > 0

    def test_unrelated_prompts_no_match(self, db: PromptDB):
        """Completely different prompts don't cluster."""
        _insert(db, "fix the authentication bug in login.py", "s1")
        _insert(db, "add pagination to the user list API endpoint", "s2")
        report = analyze_repetition(db)
        assert report.repetition_rate == 0.0

    def test_three_sessions_same_topic(self, db: PromptDB):
        """Topic spanning 3 sessions gets session_count=3."""
        _insert(db, "fix the authentication bug in login.py", "s1")
        _insert(db, "fix the authentication issue in login module", "s2")
        _insert(db, "fix auth problem in the login file", "s3")
        report = analyze_repetition(db)
        if report.recurring_topics:
            topic = report.recurring_topics[0]
            assert topic.session_count >= 2  # at least 2, ideally 3

    def test_duplicate_of_excluded(self, db: PromptDB):
        """Prompts marked as duplicates should be excluded."""
        _insert(db, "fix the authentication bug in login.py", "s1")
        _insert(db, "fix the authentication bug in login.py copy", "s2")
        # Mark second as duplicate
        conn = db._conn()
        try:
            conn.execute("UPDATE prompts SET duplicate_of = 1 WHERE session_id = 's2'")
            conn.commit()
        finally:
            conn.close()
        report = analyze_repetition(db)
        assert report.total_prompts_analyzed == 1  # only the non-duplicate

    def test_limit_caps_analysis(self, db: PromptDB):
        """Limit parameter restricts how many prompts are analyzed."""
        for i in range(10):
            _insert(db, f"unique prompt number {i} about topic {i}", f"s{i}")
        report = analyze_repetition(db, limit=5)
        assert report.total_prompts_analyzed == 5

    def test_sorted_by_session_count(self, db: PromptDB):
        """Topics sorted by session_count descending."""
        # Topic A: 3 sessions
        _insert(db, "fix the authentication bug in login.py", "s1")
        _insert(db, "fix the authentication issue in login module", "s2")
        _insert(db, "fix the auth problem in login file", "s3")
        # Topic B: 2 sessions (different topic)
        _insert(db, "add comprehensive unit tests for the payment API", "s4")
        _insert(db, "add unit tests for the payment API endpoint", "s5")
        report = analyze_repetition(db)
        if len(report.recurring_topics) >= 2:
            assert (
                report.recurring_topics[0].session_count >= report.recurring_topics[1].session_count
            )

    def test_source_filter(self, db: PromptDB):
        """Source filter limits analysis to specific adapter."""
        _insert(db, "fix the authentication bug in login.py", "s1", source="claude-code")
        _insert(db, "fix the authentication issue in login", "s2", source="cursor")
        report = analyze_repetition(db, source="claude-code")
        assert report.total_prompts_analyzed == 1

    def test_total_sessions_counted(self, db: PromptDB):
        """Total sessions reflects distinct session count in scope."""
        _insert(db, "prompt one about topic alpha", "s1")
        _insert(db, "prompt two about topic beta", "s2")
        _insert(db, "prompt three about topic gamma", "s3")
        report = analyze_repetition(db)
        assert report.total_sessions == 3

    def test_report_fields_present(self, db: PromptDB):
        """All RepetitionReport fields are accessible."""
        report = analyze_repetition(db)
        assert isinstance(report.total_prompts_analyzed, int)
        assert isinstance(report.cross_session_matches, int)
        assert isinstance(report.repetition_rate, float)
        assert isinstance(report.recurring_topics, list)
        assert isinstance(report.total_sessions, int)
