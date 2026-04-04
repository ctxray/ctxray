"""Tests for repetition terminal rendering."""

from __future__ import annotations

from ctxray.core.repetition import RecurringTopic, RepetitionReport
from ctxray.output.repetition_terminal import render_repetition_report


def _topic(
    text: str = "fix the auth bug",
    session_count: int = 3,
    total_matches: int = 5,
) -> RecurringTopic:
    return RecurringTopic(
        canonical_text=text,
        session_count=session_count,
        total_matches=total_matches,
        session_ids=[f"s{i}" for i in range(session_count)],
        earliest="2026-01-15T10:00:00Z",
        latest="2026-03-28T10:00:00Z",
    )


class TestRenderRepetitionReport:
    def test_empty_report(self):
        report = RepetitionReport()
        output = render_repetition_report(report)
        assert "no cross-session" in output.lower()

    def test_with_topics(self):
        report = RepetitionReport(
            total_prompts_analyzed=100,
            cross_session_matches=18,
            repetition_rate=0.18,
            recurring_topics=[_topic(), _topic("add unit tests", 2, 3)],
            total_sessions=10,
        )
        output = render_repetition_report(report)
        assert "Cross-Session Repetition" in output
        assert "fix the auth bug" in output
        assert "add unit tests" in output

    def test_rate_displayed(self):
        report = RepetitionReport(
            total_prompts_analyzed=50,
            cross_session_matches=10,
            repetition_rate=0.20,
            recurring_topics=[_topic()],
            total_sessions=5,
        )
        output = render_repetition_report(report)
        assert "20%" in output

    def test_long_text_truncated(self):
        long_text = "x" * 80
        report = RepetitionReport(
            total_prompts_analyzed=10,
            cross_session_matches=4,
            repetition_rate=0.4,
            recurring_topics=[_topic(long_text)],
            total_sessions=3,
        )
        output = render_repetition_report(report)
        assert "..." in output

    def test_date_range_shown(self):
        report = RepetitionReport(
            total_prompts_analyzed=10,
            cross_session_matches=4,
            repetition_rate=0.4,
            recurring_topics=[_topic()],
            total_sessions=3,
        )
        output = render_repetition_report(report)
        assert "2026-01-15" in output
        assert "2026-03-28" in output
