"""Tests for session quality terminal rendering."""

from __future__ import annotations

from ctxray.output.sessions_terminal import render_session_detail, render_sessions_table


def _mock_session(
    session_id: str = "test-session",
    quality_score: float | None = 72.0,
    **overrides: object,
) -> dict:
    base = {
        "session_id": session_id,
        "source": "claude-code",
        "project": "test",
        "quality_score": quality_score,
        "prompt_quality_score": 80.0,
        "efficiency_score": 65.0,
        "focus_score": 50.0,
        "outcome_score": 70.0,
        "session_type": "implementation",
        "prompt_count": 10,
        "error_count": 2,
        "duration_seconds": 1800,
        "quality_insight": "Solid session",
        "has_abandonment": 0,
        "has_escalation": 0,
        "stall_turns": 0,
    }
    base.update(overrides)
    return base


class TestRenderSessionsTable:
    def test_empty_list(self):
        output = render_sessions_table([])
        assert "no sessions" in output.lower() or "scan" in output.lower()

    def test_with_sessions(self):
        sessions = [_mock_session("sess-1", 85.0), _mock_session("sess-2", 42.0)]
        output = render_sessions_table(sessions)
        assert "Session Quality" in output
        assert "sess-1" in output
        assert "sess-2" in output

    def test_avg_quality_displayed(self):
        sessions = [_mock_session("s1", 80.0), _mock_session("s2", 60.0)]
        output = render_sessions_table(sessions)
        assert "70" in output  # avg of 80 and 60

    def test_null_score_shows_dash(self):
        sessions = [_mock_session("s1", None)]
        output = render_sessions_table(sessions)
        assert "\u2014" in output  # em dash

    def test_insight_displayed(self):
        sessions = [
            _mock_session("s1", insight="Focused session", quality_insight="Focused session")
        ]
        output = render_sessions_table(sessions)
        assert "Focused session" in output


class TestRenderSessionDetail:
    def test_basic_detail(self):
        output = render_session_detail(_mock_session())
        assert "Session Detail" in output
        assert "Prompt Quality" in output
        assert "Efficiency" in output
        assert "Focus" in output
        assert "Outcome" in output

    def test_frustration_abandonment(self):
        output = render_session_detail(_mock_session(has_abandonment=1))
        assert "Abandonment" in output

    def test_frustration_escalation(self):
        output = render_session_detail(_mock_session(has_escalation=1))
        assert "Escalation" in output

    def test_frustration_stalls(self):
        output = render_session_detail(_mock_session(stall_turns=3))
        assert "3 turns" in output

    def test_no_frustration(self):
        output = render_session_detail(_mock_session())
        assert "None detected" in output

    def test_null_components(self):
        output = render_session_detail(
            _mock_session(
                efficiency_score=None,
                focus_score=None,
            )
        )
        assert "not available" in output

    def test_session_info_section(self):
        output = render_session_detail(_mock_session(source="cursor", session_type="debugging"))
        assert "cursor" in output
        assert "debugging" in output
