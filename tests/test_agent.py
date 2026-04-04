"""Tests for agent workflow analysis engine."""

from __future__ import annotations

from ctxray.core.agent import (
    AgentReport,
    AggregateAgentReport,
    ErrorLoop,
    analyze_session,
    analyze_sessions,
    compute_efficiency,
    compute_tool_distribution,
    detect_error_loops,
)
from ctxray.core.conversation import Conversation, ConversationTurn


def _user(idx: int, text: str = "do something", ts: str = "") -> ConversationTurn:
    return ConversationTurn(role="user", text=text, timestamp=ts, turn_index=idx)


def _asst(
    idx: int,
    tool_names: list[str] | None = None,
    has_error: bool = False,
    tool_use_paths: list[str] | None = None,
    error_text: str = "",
    text: str = "ok",
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
        error_text=error_text,
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


# ---------------------------------------------------------------------------
# Error loop detection
# ---------------------------------------------------------------------------


class TestDetectErrorLoops:
    def test_no_loops_clean_session(self):
        turns = [
            _user(0),
            _asst(1, ["Read"]),
            _user(2),
            _asst(3, ["Edit"]),
            _user(4),
            _asst(5, ["Bash"]),
        ]
        assert detect_error_loops(turns) == []

    def test_single_step_loop_3_repeats(self):
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True, tool_use_paths=["tests/test_auth.py"]),
            _user(2),
            _asst(3, ["Bash"], has_error=True, tool_use_paths=["tests/test_auth.py"]),
            _user(4),
            _asst(5, ["Bash"], has_error=True, tool_use_paths=["tests/test_auth.py"]),
        ]
        loops = detect_error_loops(turns)
        assert len(loops) == 1
        assert loops[0].loop_count == 3
        assert loops[0].tool_name == "Bash"

    def test_single_step_loop_not_triggered_for_2_repeats(self):
        """Two repeats is not enough for a single-step loop."""
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True),
            _user(2),
            _asst(3, ["Bash"], has_error=True),
        ]
        assert detect_error_loops(turns) == []

    def test_two_step_loop(self):
        """A→B→A→B pattern should be detected as a 2-step loop."""
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
            _asst(2, ["Edit"], tool_use_paths=["src/auth.py"]),
            _asst(3, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
            _asst(4, ["Edit"], tool_use_paths=["src/auth.py"]),
        ]
        loops = detect_error_loops(turns)
        assert len(loops) == 1
        assert loops[0].loop_count == 2

    def test_two_step_loop_3_repeats(self):
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True, tool_use_paths=["t.py"]),
            _asst(2, ["Edit"], tool_use_paths=["s.py"]),
            _asst(3, ["Bash"], has_error=True, tool_use_paths=["t.py"]),
            _asst(4, ["Edit"], tool_use_paths=["s.py"]),
            _asst(5, ["Bash"], has_error=True, tool_use_paths=["t.py"]),
            _asst(6, ["Edit"], tool_use_paths=["s.py"]),
        ]
        loops = detect_error_loops(turns)
        assert len(loops) == 1
        assert loops[0].loop_count == 3

    def test_empty_session(self):
        assert detect_error_loops([]) == []

    def test_user_only_session(self):
        turns = [_user(0), _user(1), _user(2)]
        assert detect_error_loops(turns) == []

    def test_single_turn_session(self):
        turns = [_user(0), _asst(1, ["Read"])]
        assert detect_error_loops(turns) == []

    def test_text_only_assistant_turns_ignored(self):
        """Assistant turns without tool calls should not form loops."""
        turns = [
            _user(0),
            _asst(1, text="Error: something failed"),
            _user(2),
            _asst(3, text="Error: something failed"),
            _user(4),
            _asst(5, text="Error: something failed"),
        ]
        assert detect_error_loops(turns) == []

    def test_mixed_tools_no_loop(self):
        """Different tools each time should not be detected as a loop."""
        turns = [
            _user(0),
            _asst(1, ["Read"]),
            _user(2),
            _asst(3, ["Edit"]),
            _user(4),
            _asst(5, ["Bash"]),
            _user(6),
            _asst(7, ["Grep"]),
        ]
        assert detect_error_loops(turns) == []

    def test_loop_with_different_files_not_loop(self):
        """Same tool but different target files should not be a loop."""
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True, tool_use_paths=["test_a.py"]),
            _user(2),
            _asst(3, ["Bash"], has_error=True, tool_use_paths=["test_b.py"]),
            _user(4),
            _asst(5, ["Bash"], has_error=True, tool_use_paths=["test_c.py"]),
        ]
        assert detect_error_loops(turns) == []

    def test_loop_fingerprint_includes_error_state(self):
        """Same tool+file but without error should not match error fingerprint."""
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
            _user(2),
            _asst(3, ["Bash"], has_error=False, tool_use_paths=["test.py"]),  # no error
            _user(4),
            _asst(5, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
        ]
        assert detect_error_loops(turns) == []


# ---------------------------------------------------------------------------
# Tool distribution
# ---------------------------------------------------------------------------


class TestToolDistribution:
    def test_basic_distribution(self):
        turns = [
            _asst(0, ["Read", "Read", "Edit"]),
            _asst(1, ["Bash"]),
            _asst(2, ["Read"]),
        ]
        dist = compute_tool_distribution(turns)
        assert dist == {"Read": 3, "Edit": 1, "Bash": 1}

    def test_empty_turns(self):
        assert compute_tool_distribution([]) == {}

    def test_user_turns_ignored(self):
        turns = [_user(0), _user(1)]
        assert compute_tool_distribution(turns) == {}

    def test_no_tools(self):
        turns = [_asst(0, text="Just text, no tools")]
        assert compute_tool_distribution(turns) == {}

    def test_sorted_by_frequency(self):
        turns = [_asst(0, ["Bash", "Bash", "Bash", "Read", "Edit", "Edit"])]
        dist = compute_tool_distribution(turns)
        keys = list(dist.keys())
        assert keys[0] == "Bash"
        assert keys[1] == "Edit"
        assert keys[2] == "Read"


# ---------------------------------------------------------------------------
# Efficiency scoring
# ---------------------------------------------------------------------------


class TestEfficiency:
    def test_clean_session(self):
        turns = [_user(0), _asst(1, ["Read"]), _user(2), _asst(3, ["Edit"])]
        eff = compute_efficiency(turns, [], duration_seconds=600)
        assert eff.total_turns == 4
        assert eff.user_turns == 2
        assert eff.tool_calls == 2
        assert eff.errors == 0
        assert eff.productive_ratio == 1.0
        assert eff.error_recovery_rate == 1.0

    def test_session_with_errors(self):
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True),
            _user(2),
            _asst(3, ["Bash"], has_error=True),
            _user(4),
            _asst(5, ["Edit"]),
        ]
        eff = compute_efficiency(turns, [])
        assert eff.errors == 2
        assert eff.productive_ratio == 1.0  # No loops detected

    def test_session_with_loops(self):
        turns = [
            _user(0),
            _asst(1, ["Bash"], has_error=True),
            _user(2),
            _asst(3, ["Bash"], has_error=True),
            _user(4),
            _asst(5, ["Bash"], has_error=True),
            _user(6),
            _asst(7, ["Edit"]),
        ]
        loop = ErrorLoop(
            start_turn=1,
            end_turn=5,
            loop_count=3,
            fingerprint="Bash:err",
            tool_name="Bash",
            description="test",
        )
        eff = compute_efficiency(turns, [loop])
        assert eff.turns_in_loops > 0
        assert eff.productive_ratio < 1.0

    def test_empty_session(self):
        eff = compute_efficiency([], [])
        assert eff.total_turns == 0
        assert eff.productive_ratio == 1.0

    def test_tools_per_user_turn(self):
        turns = [
            _user(0),
            _asst(1, ["Read", "Edit", "Bash"]),  # 3 tools
            _user(2),
            _asst(3, ["Read"]),  # 1 tool
        ]
        eff = compute_efficiency(turns, [])
        assert eff.tools_per_user_turn == 2.0  # 4 tools / 2 user turns

    def test_recovery_rate_resolved(self):
        """Loop resolved = session continues after loop ends."""
        turns = [_user(i) for i in range(10)]  # 10 turns, loop ends at turn 5
        loop = ErrorLoop(
            start_turn=1,
            end_turn=5,
            loop_count=3,
            fingerprint="test",
            tool_name="Bash",
            description="test",
        )
        eff = compute_efficiency(turns, [loop])
        assert eff.error_recovery_rate == 1.0  # Loop ends before last turn

    def test_recovery_rate_unresolved(self):
        """Loop unresolved = loop ends at session end."""
        turns = [_user(0), _asst(1), _asst(2)]
        loop = ErrorLoop(
            start_turn=1,
            end_turn=2,
            loop_count=3,
            fingerprint="test",
            tool_name="Bash",
            description="test",
        )
        eff = compute_efficiency(turns, [loop])
        assert eff.error_recovery_rate == 0.0


# ---------------------------------------------------------------------------
# Session analysis (integration)
# ---------------------------------------------------------------------------


class TestAnalyzeSession:
    def test_returns_agent_report(self):
        turns = [
            _user(0, "Fix the auth bug"),
            _asst(1, ["Read"], tool_use_paths=["src/auth.py"]),
            _user(2, "Now add tests"),
            _asst(3, ["Edit", "Write"], tool_use_paths=["src/auth.py", "tests/test_auth.py"]),
        ]
        conv = _conv(turns)
        report = analyze_session(conv)
        assert isinstance(report, AgentReport)
        assert report.session_id == "test-session"
        assert report.tool_distribution == {"Read": 1, "Edit": 1, "Write": 1}
        assert report.error_loops == []
        assert "src/auth.py" in report.top_files

    def test_detects_loops_in_real_session(self):
        turns = [
            _user(0, "Run tests"),
            _asst(1, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
            _user(2, "Try again"),
            _asst(3, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
            _user(4, "One more time"),
            _asst(5, ["Bash"], has_error=True, tool_use_paths=["test.py"]),
            _user(6, "Let me try a different approach"),
            _asst(7, ["Edit"], tool_use_paths=["src/fix.py"]),
        ]
        conv = _conv(turns)
        report = analyze_session(conv)
        assert len(report.error_loops) == 1
        assert report.efficiency.error_loops == 1
        assert report.efficiency.productive_ratio < 1.0


class TestAnalyzeSessions:
    def test_multi_session_rollup(self):
        conv1 = _conv(
            [_user(0), _asst(1, ["Read"]), _user(2), _asst(3, ["Edit"])],
            sid="session-1",
        )
        conv2 = _conv(
            [_user(0), _asst(1, ["Bash"]), _user(2), _asst(3, ["Bash"])],
            sid="session-2",
        )
        agg = analyze_sessions([conv1, conv2])
        assert isinstance(agg, AggregateAgentReport)
        assert agg.sessions_analyzed == 2
        assert agg.total_turns == 8
        assert agg.total_tool_calls == 4
        assert len(agg.sessions) == 2

    def test_empty_sessions(self):
        agg = analyze_sessions([])
        assert agg.sessions_analyzed == 0
        assert agg.total_turns == 0

    def test_tool_distribution_merged(self):
        conv1 = _conv([_asst(0, ["Read", "Read"])], sid="s1")
        conv2 = _conv([_asst(0, ["Read", "Bash"])], sid="s2")
        agg = analyze_sessions([conv1, conv2])
        assert agg.tool_distribution["Read"] == 3
        assert agg.tool_distribution["Bash"] == 1
