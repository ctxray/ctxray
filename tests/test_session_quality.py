"""Tests for session-level quality metrics."""

from __future__ import annotations

from ctxray.core.agent import AgentEfficiency, AgentReport
from ctxray.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)
from ctxray.core.session_quality import (
    FrustrationSignals,
    SessionQuality,
    _detect_frustration,
    _generate_insight,
    score_session,
)

# ---------------------------------------------------------------------------
# Helpers (reuse pattern from test_agent.py)
# ---------------------------------------------------------------------------


def _user(idx: int, text: str = "do something", ts: str = "") -> ConversationTurn:
    return ConversationTurn(role="user", text=text, timestamp=ts, turn_index=idx)


def _asst(
    idx: int,
    tool_names: list[str] | None = None,
    has_error: bool = False,
    text: str = "ok",
    tool_use_paths: list[str] | None = None,
) -> ConversationTurn:
    names = tool_names or []
    return ConversationTurn(
        role="assistant",
        text=text,
        timestamp="",
        turn_index=idx,
        tool_calls=len(names),
        has_error=has_error,
        tool_use_paths=tool_use_paths or [],
        tool_names=names,
    )


def _conv(turns: list[ConversationTurn], sid: str = "test-session") -> Conversation:
    return Conversation(
        session_id=sid,
        source="claude-code",
        project="test-project",
        turns=turns,
        start_time="2026-03-28T10:00:00Z",
        end_time="2026-03-28T10:30:00Z",
        duration_seconds=1800,
    )


def _agent_report(
    productive_ratio: float = 0.8,
    error_loops: int = 0,
    session_type: str | None = "implementation",
) -> AgentReport:
    return AgentReport(
        session_id="test-session",
        source="claude-code",
        project="test-project",
        efficiency=AgentEfficiency(
            total_turns=20,
            user_turns=10,
            tool_calls=15,
            errors=2,
            error_loops=error_loops,
            turns_in_loops=error_loops * 3,
            productive_ratio=productive_ratio,
            tools_per_user_turn=1.5,
            error_recovery_rate=1.0,
            duration_seconds=1800,
            session_type=session_type,
        ),
        tool_distribution={"Read": 5, "Edit": 4, "Bash": 6},
        error_loops=[],
        top_files=["main.py"],
    )


def _distill_result(retention_ratio: float = 0.5) -> DistillResult:
    conv = _conv([_user(0), _asst(1, ["Read"])])
    return DistillResult(
        conversation=conv,
        filtered_turns=[],
        threshold=0.3,
        stats=DistillStats(
            total_turns=20,
            kept_turns=int(20 * retention_ratio),
            retention_ratio=retention_ratio,
            total_duration_seconds=1800,
        ),
    )


# ---------------------------------------------------------------------------
# TestFrustrationSignals
# ---------------------------------------------------------------------------


class TestFrustrationSignals:
    def test_clean_session_no_frustration(self):
        turns = [
            _user(0),
            _asst(1, ["Read"]),
            _user(2),
            _asst(3, ["Edit"]),
            _user(4),
            _asst(5, ["Bash"]),
        ]
        f = _detect_frustration(turns)
        assert f.abandonment is False
        assert f.escalation is False
        assert f.stall_turns == 0

    def test_abandonment_last_three_errors(self):
        turns = [
            _user(0),
            _asst(1, ["Read"]),
            _user(2),
            _asst(3, ["Bash"], has_error=True),
            _user(4),
            _asst(5, ["Bash"], has_error=True),
            _user(6),
            _asst(7, ["Bash"], has_error=True),
        ]
        f = _detect_frustration(turns)
        assert f.abandonment is True

    def test_no_abandonment_last_two_errors(self):
        """Need 3+ consecutive errors at end, not just 2."""
        turns = [
            _user(0),
            _asst(1, ["Read"]),
            _user(2),
            _asst(3, ["Bash"], has_error=True),
            _user(4),
            _asst(5, ["Bash"], has_error=True),
        ]
        f = _detect_frustration(turns)
        # Only 2 assistant turns with errors at end, but there are only
        # 3 total assistant turns and last 3 includes a non-error one
        assert f.abandonment is False

    def test_escalation_detected(self):
        """Error rate increases from first half to second half."""
        turns = []
        idx = 0
        # First half: 8 assistant turns, 1 error (12.5%)
        for i in range(8):
            turns.append(_user(idx, text="prompt"))
            idx += 1
            turns.append(_asst(idx, ["Read"], has_error=(i == 0)))
            idx += 1
        # Second half: 8 assistant turns, 6 errors (75%)
        for i in range(8):
            turns.append(_user(idx, text="prompt"))
            idx += 1
            turns.append(_asst(idx, ["Bash"], has_error=(i < 6)))
            idx += 1
        f = _detect_frustration(turns)
        assert f.escalation is True

    def test_no_escalation_steady_errors(self):
        """Same error rate throughout — no escalation."""
        turns = []
        idx = 0
        for i in range(8):
            turns.append(_user(idx))
            idx += 1
            turns.append(_asst(idx, ["Read"], has_error=(i % 2 == 0)))
            idx += 1
        f = _detect_frustration(turns)
        assert f.escalation is False

    def test_stall_turns_counted(self):
        turns = [
            _user(0),
            _asst(1, text="ok"),  # stall: no tools, <50 chars
            _user(2),
            _asst(3, text="I see"),  # stall
            _user(4),
            _asst(5, ["Read"], text="Reading file..."),  # not stall (has tool)
            _user(6),
            _asst(7, text="x" * 100),  # not stall (long text)
        ]
        f = _detect_frustration(turns)
        assert f.stall_turns == 2

    def test_empty_turns(self):
        f = _detect_frustration([])
        assert f.abandonment is False
        assert f.escalation is False
        assert f.stall_turns == 0

    def test_no_assistant_turns(self):
        turns = [_user(0), _user(1), _user(2)]
        f = _detect_frustration(turns)
        assert f.abandonment is False
        assert f.stall_turns == 0


# ---------------------------------------------------------------------------
# TestScoreSession
# ---------------------------------------------------------------------------


class TestScoreSession:
    def test_all_components_perfect(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(
            conv,
            agent_report=_agent_report(productive_ratio=1.0),
            distill_result=_distill_result(retention_ratio=1.0),
            effectiveness_score=1.0,
            avg_prompt_score=100.0,
        )
        assert q.quality_score == 100.0
        assert q.prompt_quality == 100.0
        assert q.efficiency == 100.0
        assert q.focus == 100.0
        assert q.outcome == 100.0
        assert q.components_available == 4

    def test_all_components_zero(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(
            conv,
            agent_report=_agent_report(productive_ratio=0.0),
            distill_result=_distill_result(retention_ratio=0.0),
            effectiveness_score=0.0,
            avg_prompt_score=0.0,
        )
        assert q.quality_score == 0.0
        assert q.components_available == 4

    def test_partial_components_only_prompt_quality(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(conv, avg_prompt_score=75.0)
        assert q.quality_score == 75.0
        assert q.prompt_quality == 75.0
        assert q.efficiency is None
        assert q.focus is None
        assert q.outcome is None
        assert q.components_available == 1

    def test_partial_components_two_available(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(
            conv,
            avg_prompt_score=80.0,
            effectiveness_score=0.6,
        )
        # prompt_quality=80, outcome=60
        # Weights: prompt_quality=0.30, outcome=0.20, total=0.50
        # Normalized: pq=0.60, outcome=0.40
        # Score = 80*0.60 + 60*0.40 = 48+24 = 72
        assert q.quality_score == 72.0
        assert q.components_available == 2

    def test_no_components_score_zero(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(conv)
        assert q.quality_score == 0.0
        assert q.components_available == 0

    def test_score_clamped_to_100(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(conv, avg_prompt_score=150.0)  # over 100
        assert q.quality_score == 100.0

    def test_score_clamped_to_0(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(conv, avg_prompt_score=-10.0)
        assert q.quality_score == 0.0

    def test_session_type_from_agent_report(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(
            conv,
            agent_report=_agent_report(session_type="debugging"),
        )
        assert q.session_type == "debugging"

    def test_session_type_none_without_agent(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(conv, avg_prompt_score=50.0)
        assert q.session_type is None

    def test_frustration_detected_in_score(self):
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True),
            _user(2),
            _asst(3, ["Bash"], has_error=True),
            _user(4),
            _asst(5, ["Bash"], has_error=True),
        ]
        conv = _conv(turns)
        q = score_session(conv, avg_prompt_score=50.0)
        assert q.frustration.abandonment is True

    def test_weighted_average_mixed(self):
        conv = _conv([_user(0), _asst(1, ["Read"])])
        q = score_session(
            conv,
            agent_report=_agent_report(productive_ratio=0.9),
            distill_result=_distill_result(retention_ratio=0.4),
            effectiveness_score=0.7,
            avg_prompt_score=60.0,
        )
        # pq=60*0.30 + eff=90*0.30 + focus=40*0.20 + outcome=70*0.20
        # = 18 + 27 + 8 + 14 = 67
        assert q.quality_score == 67.0


# ---------------------------------------------------------------------------
# TestInsightGeneration
# ---------------------------------------------------------------------------


class TestInsightGeneration:
    def test_abandonment_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=30.0,
            frustration=FrustrationSignals(abandonment=True),
        )
        assert "unresolved errors" in _generate_insight(q).lower()

    def test_escalation_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=40.0,
            frustration=FrustrationSignals(escalation=True),
        )
        assert "escalat" in _generate_insight(q).lower()

    def test_stall_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=50.0,
            frustration=FrustrationSignals(stall_turns=7),
        )
        assert "7 stall" in _generate_insight(q)

    def test_low_efficiency_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=45.0,
            efficiency=30.0,
            frustration=FrustrationSignals(),
        )
        assert "efficiency" in _generate_insight(q).lower()

    def test_high_score_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=85.0,
            frustration=FrustrationSignals(),
        )
        assert _generate_insight(q) == "Focused session"

    def test_solid_score_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=65.0,
            frustration=FrustrationSignals(),
        )
        assert _generate_insight(q) == "Solid session"

    def test_mid_score_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=45.0,
            frustration=FrustrationSignals(),
        )
        assert _generate_insight(q) == "Room for improvement"

    def test_low_score_insight(self):
        q = SessionQuality(
            session_id="t",
            quality_score=20.0,
            frustration=FrustrationSignals(),
        )
        assert _generate_insight(q) == "Rough session"

    def test_abandonment_overrides_score(self):
        """Abandonment insight takes priority even with high score."""
        q = SessionQuality(
            session_id="t",
            quality_score=90.0,
            frustration=FrustrationSignals(abandonment=True),
        )
        assert "unresolved errors" in _generate_insight(q).lower()


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_conversation(self):
        conv = _conv([])
        q = score_session(conv, avg_prompt_score=50.0)
        assert q.quality_score == 50.0
        assert q.frustration.abandonment is False
        assert q.frustration.stall_turns == 0

    def test_single_turn_conversation(self):
        conv = _conv([_user(0, text="hello")])
        q = score_session(conv, avg_prompt_score=40.0)
        assert q.quality_score == 40.0

    def test_only_user_turns(self):
        turns = [_user(i) for i in range(5)]
        conv = _conv(turns)
        q = score_session(conv)
        assert q.quality_score == 0.0
        assert q.frustration.stall_turns == 0

    def test_only_assistant_turns(self):
        turns = [_asst(i, ["Read"]) for i in range(3)]
        conv = _conv(turns)
        q = score_session(conv)
        assert q.quality_score == 0.0
        assert q.frustration.abandonment is False

    def test_efficiency_clamped_above_1(self):
        """productive_ratio > 1.0 should clamp efficiency to 100."""
        conv = _conv([_user(0), _asst(1, ["Read"])])
        report = _agent_report(productive_ratio=1.5)
        q = score_session(conv, agent_report=report)
        assert q.efficiency == 100.0

    def test_focus_clamped_above_1(self):
        """retention_ratio > 1.0 should clamp focus to 100."""
        conv = _conv([_user(0), _asst(1, ["Read"])])
        result = _distill_result(retention_ratio=1.2)
        q = score_session(conv, distill_result=result)
        assert q.focus == 100.0

    def test_session_id_propagated(self):
        conv = _conv([_user(0)], sid="my-session-123")
        q = score_session(conv, avg_prompt_score=50.0)
        assert q.session_id == "my-session-123"
