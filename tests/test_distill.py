"""Tests for the distill scoring engine."""

from __future__ import annotations

from reprompt.core.conversation import Conversation, ConversationTurn, DistillResult, DistillStats


def _make_conv(user_texts: list[str], assistant_texts: list[str] | None = None) -> Conversation:
    """Helper: build a Conversation from interleaved user/assistant text lists."""
    turns = []
    idx = 0
    for i, text in enumerate(user_texts):
        turns.append(ConversationTurn(role="user", text=text, timestamp="", turn_index=idx))
        idx += 1
        if assistant_texts and i < len(assistant_texts):
            turns.append(
                ConversationTurn(
                    role="assistant",
                    text=assistant_texts[i],
                    timestamp="",
                    turn_index=idx,
                )
            )
            idx += 1
    return Conversation(session_id="test", source="claude-code", project="test", turns=turns)


class TestPositionSignal:
    def test_first_turn_highest(self):
        from reprompt.core.distill import _score_position

        assert _score_position(0, 10) == 1.0

    def test_last_turn_high(self):
        from reprompt.core.distill import _score_position

        assert _score_position(9, 10) == 0.8

    def test_middle_turn_lower(self):
        from reprompt.core.distill import _score_position

        score = _score_position(5, 10)
        assert 0.3 < score < 0.8


class TestLengthSignal:
    def test_longer_than_median_capped(self):
        from reprompt.core.distill import _score_length

        assert _score_length(200, 100) == 1.0

    def test_shorter_than_median(self):
        from reprompt.core.distill import _score_length

        score = _score_length(50, 100)
        assert score == 0.5

    def test_zero_median(self):
        from reprompt.core.distill import _score_length

        assert _score_length(10, 0) == 1.0


class TestToolTriggerSignal:
    def test_five_or_more_maxes_out(self):
        from reprompt.core.distill import _score_tool_trigger

        assert _score_tool_trigger(5) == 1.0
        assert _score_tool_trigger(10) == 1.0

    def test_zero_tool_calls(self):
        from reprompt.core.distill import _score_tool_trigger

        assert _score_tool_trigger(0) == 0.0

    def test_partial(self):
        from reprompt.core.distill import _score_tool_trigger

        assert _score_tool_trigger(2) == 0.4


class TestErrorRecoverySignal:
    def test_after_error(self):
        from reprompt.core.distill import _score_error_recovery

        assert _score_error_recovery(True) == 1.0

    def test_no_error(self):
        from reprompt.core.distill import _score_error_recovery

        assert _score_error_recovery(False) == 0.0


class TestDistillConversation:
    def test_basic_distill(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(
            [
                "Implement the auth system with JWT tokens and refresh token rotation",
                "ok",
                "Fix the error in login.py -- TypeError on line 42",
                "Now add comprehensive tests for all auth endpoints",
            ],
            [
                "I'll implement JWT auth...",
                "Done.",
                "Fixed the TypeError...",
                "Here are the tests...",
            ],
        )
        result = distill_conversation(conv, threshold=0.3)
        assert result.stats.total_turns > 0
        assert result.stats.kept_turns <= result.stats.total_turns
        assert 0.0 <= result.stats.retention_ratio <= 1.0

    def test_short_turns_scored_lower(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(
            [
                "Implement a complete user authentication system with OAuth2",
                "ok",
                "yes",
                "Build the database migration for the users table with indexes",
            ],
        )
        result = distill_conversation(conv, threshold=0.0)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        assert user_turns[0].importance > user_turns[1].importance
        assert user_turns[0].importance > user_turns[2].importance

    def test_threshold_filtering(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["hello"] * 10)
        result_low = distill_conversation(conv, threshold=0.0)
        result_high = distill_conversation(conv, threshold=0.9)
        assert result_low.stats.kept_turns >= result_high.stats.kept_turns

    def test_empty_conversation(self):
        from reprompt.core.distill import distill_conversation

        conv = Conversation(session_id="empty", source="test", project=None, turns=[])
        result = distill_conversation(conv, threshold=0.3)
        assert result.filtered_turns == []
        assert result.stats.total_turns == 0

    def test_single_turn_always_kept(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["Fix the critical production bug immediately"])
        result = distill_conversation(conv, threshold=0.3)
        assert result.stats.kept_turns >= 1

    def test_single_turn_kept_even_at_high_threshold(self):
        """Spec guarantee: single-turn conversations always pass any threshold."""
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["ok"])
        result = distill_conversation(conv, threshold=0.99)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        assert user_turns[0].importance == 1.0
        assert result.stats.kept_turns >= 1

    def test_all_below_threshold(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["ok", "yes", "k"])
        result = distill_conversation(conv, threshold=0.99)
        assert result.stats.kept_turns == 0
        assert result.filtered_turns == []

    def test_tool_trigger_boosts_importance(self):
        from reprompt.core.distill import distill_conversation

        turns = [
            ConversationTurn(
                role="user",
                text="Implement feature X with full test coverage",
                timestamp="",
                turn_index=0,
            ),
            ConversationTurn(
                role="assistant", text="Implementing...", timestamp="", turn_index=1, tool_calls=8
            ),
            ConversationTurn(
                role="user",
                text="Implement feature Y with full test coverage",
                timestamp="",
                turn_index=2,
            ),
            ConversationTurn(
                role="assistant", text="Done.", timestamp="", turn_index=3, tool_calls=0
            ),
        ]
        conv = Conversation(session_id="test", source="test", project=None, turns=turns)
        result = distill_conversation(conv, threshold=0.0)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        assert user_turns[0].importance > user_turns[1].importance

    def test_error_recovery_boosts_importance(self):
        from reprompt.core.distill import distill_conversation

        turns = [
            ConversationTurn(
                role="user", text="Run the migration script", timestamp="", turn_index=0
            ),
            ConversationTurn(
                role="assistant",
                text="Error: connection refused",
                timestamp="",
                turn_index=1,
                has_error=True,
            ),
            ConversationTurn(
                role="user",
                text="Use localhost:5432 instead of the remote host",
                timestamp="",
                turn_index=2,
            ),
            ConversationTurn(
                role="assistant", text="Migration complete.", timestamp="", turn_index=3
            ),
        ]
        conv = Conversation(session_id="test", source="test", project=None, turns=turns)
        result = distill_conversation(conv, threshold=0.0)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        assert user_turns[1].importance > 0.3


class TestFilesChanged:
    def test_extracts_edit_write_paths(self):
        from reprompt.core.distill import _extract_files_changed

        turns = [
            ConversationTurn(
                role="assistant",
                text="editing",
                timestamp="",
                turn_index=0,
                tool_use_paths=["src/auth.py", "src/auth.py", "tests/test_auth.py"],
            ),
            ConversationTurn(
                role="assistant",
                text="more",
                timestamp="",
                turn_index=1,
                tool_use_paths=["src/db.py"],
            ),
        ]
        files = _extract_files_changed(turns)
        assert files == ["src/auth.py", "src/db.py", "tests/test_auth.py"]

    def test_empty_turns(self):
        from reprompt.core.distill import _extract_files_changed

        assert _extract_files_changed([]) == []


class TestGenerateSummary:
    def test_summary_basic(self):
        from reprompt.core.distill import generate_summary

        turns = [
            ConversationTurn(
                role="user",
                text="Implement the authentication system with JWT",
                timestamp="",
                turn_index=0,
                importance=0.9,
            ),
            ConversationTurn(
                role="assistant",
                text="I'll implement JWT auth...",
                timestamp="",
                turn_index=1,
                tool_use_paths=["src/auth.py"],
            ),
            ConversationTurn(
                role="user",
                text="Add refresh token rotation",
                timestamp="",
                turn_index=2,
                importance=0.7,
            ),
        ]
        conv = Conversation(
            session_id="test",
            source="claude-code",
            project="myproject",
            turns=turns,
            duration_seconds=1800,
        )
        result = DistillResult(
            conversation=conv,
            filtered_turns=turns,
            threshold=0.3,
            files_changed=["src/auth.py"],
            stats=DistillStats(
                total_turns=3, kept_turns=3, retention_ratio=1.0, total_duration_seconds=1800
            ),
        )
        summary = generate_summary(result)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_includes_files(self):
        from reprompt.core.distill import generate_summary

        turns = [
            ConversationTurn(
                role="user", text="Fix the bug", timestamp="", turn_index=0, importance=0.9
            ),
        ]
        conv = Conversation(session_id="t", source="test", project=None, turns=turns)
        result = DistillResult(
            conversation=conv,
            filtered_turns=turns,
            threshold=0.3,
            files_changed=["src/auth.py", "src/db.py"],
            stats=DistillStats(total_turns=1, kept_turns=1),
        )
        summary = generate_summary(result)
        assert "src/auth.py" in summary

    def test_summary_empty_conversation(self):
        from reprompt.core.distill import generate_summary

        conv = Conversation(session_id="t", source="test", project=None, turns=[])
        result = DistillResult(
            conversation=conv,
            filtered_turns=[],
            threshold=0.3,
            stats=DistillStats(),
        )
        summary = generate_summary(result)
        assert isinstance(summary, str)


class TestDistillEdgeCases:
    def test_conversation_only_assistant_turns(self):
        """Conversation with no user turns should produce empty result."""
        from reprompt.core.distill import distill_conversation

        turns = [
            ConversationTurn(role="assistant", text="hello", timestamp="", turn_index=0),
        ]
        conv = Conversation(session_id="test", source="test", project=None, turns=turns)
        result = distill_conversation(conv, threshold=0.3)
        assert result.stats.kept_turns == 0

    def test_very_long_conversation(self):
        """50+ turns should not crash or take too long."""
        from reprompt.core.distill import distill_conversation

        turns = []
        for i in range(100):
            turns.append(
                ConversationTurn(
                    role="user",
                    text=f"Task {i}: implement feature number {i} with tests",
                    timestamp="",
                    turn_index=i * 2,
                )
            )
            turns.append(
                ConversationTurn(
                    role="assistant",
                    text=f"Implementing feature {i}...",
                    timestamp="",
                    turn_index=i * 2 + 1,
                    tool_calls=i % 5,
                )
            )
        conv = Conversation(session_id="long", source="test", project=None, turns=turns)
        result = distill_conversation(conv, threshold=0.3)
        assert result.stats.total_turns == 200
        assert result.stats.kept_turns > 0

    def test_identical_user_turns(self):
        """All identical turns — uniqueness signal should differentiate."""
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["fix the bug"] * 5)
        result = distill_conversation(conv, threshold=0.0)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        # First turn should have highest importance (position + uniqueness)
        assert user_turns[0].importance >= user_turns[-1].importance

    def test_duration_computed(self):
        """Verify duration_seconds works in generate_summary."""
        from reprompt.core.distill import distill_conversation, generate_summary

        conv = _make_conv(["implement auth"])
        conv.duration_seconds = 3600
        result = distill_conversation(conv, threshold=0.0)
        result.summary = generate_summary(result)
        assert "60min" in result.summary

    def test_threshold_zero_keeps_all(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["a", "b", "c"])
        result = distill_conversation(conv, threshold=0.0)
        user_kept = [t for t in result.filtered_turns if t.role == "user"]
        assert len(user_kept) == 3

    def test_threshold_one_keeps_none(self):
        from reprompt.core.distill import distill_conversation

        conv = _make_conv(["short", "tiny", "ok"])
        result = distill_conversation(conv, threshold=1.0)
        assert result.stats.kept_turns == 0


# --- Signal Quality Fix Tests ---


class TestPositionGreetingSkip:
    """Position signal should not boost greeting/sign-off turns."""

    def test_greeting_first_turn_no_boost(self):
        """'hey' as first turn should get position=0.0."""
        from reprompt.core.distill import _score_position_with_text

        assert _score_position_with_text(0, 5, "hey there") == 0.0

    def test_chinese_greeting_no_boost(self):
        from reprompt.core.distill import _score_position_with_text

        assert _score_position_with_text(0, 5, "你好") == 0.0

    def test_signoff_last_turn_no_boost(self):
        from reprompt.core.distill import _score_position_with_text

        assert _score_position_with_text(4, 5, "thanks!") == 0.0

    def test_chinese_signoff_no_boost(self):
        from reprompt.core.distill import _score_position_with_text

        assert _score_position_with_text(4, 5, "谢谢收工") == 0.0

    def test_lgtm_signoff_no_boost(self):
        from reprompt.core.distill import _score_position_with_text

        assert _score_position_with_text(4, 5, "lgtm") == 0.0

    def test_substantive_first_turn_keeps_boost(self):
        from reprompt.core.distill import _score_position_with_text

        score = _score_position_with_text(0, 5, "implement auth module with JWT")
        assert score == 1.0

    def test_substantive_last_turn_keeps_boost(self):
        from reprompt.core.distill import _score_position_with_text

        score = _score_position_with_text(4, 5, "commit the changes and run tests")
        assert score == 0.8

    def test_middle_turn_unaffected(self):
        """Middle turns don't check greeting/signoff patterns."""
        from reprompt.core.distill import _score_position_with_text

        score_greeting = _score_position_with_text(2, 5, "hey")
        score_normal = _score_position_with_text(2, 5, "fix the bug")
        # Middle turns use recency formula regardless
        assert score_greeting == score_normal


class TestLengthUserOnly:
    """Length signal should only score user turns."""

    def test_user_turn_scored(self):
        """User turn length is used for scoring."""
        from reprompt.core.distill import _score_length

        assert _score_length(200, 100.0, role="user") > 0

    def test_assistant_turn_zero(self):
        """Assistant turn always gets 0.0 length score."""
        from reprompt.core.distill import _score_length

        assert _score_length(5000, 100.0, role="assistant") == 0.0


class TestErrorRecoveryFilter:
    """Error recovery should filter low-information responses."""

    def test_substantive_recovery_scores_high(self):
        from reprompt.core.distill import _score_error_recovery_with_text

        score = _score_error_recovery_with_text(True, "try using optional chaining on line 42")
        assert score == 1.0

    def test_ok_try_again_filtered(self):
        from reprompt.core.distill import _score_error_recovery_with_text

        assert _score_error_recovery_with_text(True, "ok try again") == 0.0

    def test_chinese_continue_filtered(self):
        from reprompt.core.distill import _score_error_recovery_with_text

        assert _score_error_recovery_with_text(True, "继续") == 0.0

    def test_retry_filtered(self):
        from reprompt.core.distill import _score_error_recovery_with_text

        assert _score_error_recovery_with_text(True, "retry") == 0.0

    def test_short_yes_filtered(self):
        from reprompt.core.distill import _score_error_recovery_with_text

        assert _score_error_recovery_with_text(True, "yes") == 0.0

    def test_no_error_still_zero(self):
        from reprompt.core.distill import _score_error_recovery_with_text

        assert _score_error_recovery_with_text(False, "try using optional chaining") == 0.0
