"""Tests for session type detection."""

from reprompt.core.conversation import Conversation, ConversationTurn
from reprompt.core.session_type import (
    SessionType,
    detect_session_type,
    get_weights_for_type,
)


def _make_conv(turns: list[ConversationTurn]) -> Conversation:
    return Conversation(session_id="test", source="test", project=None, turns=turns)


def _user(idx: int, text: str) -> ConversationTurn:
    return ConversationTurn(role="user", text=text, timestamp="", turn_index=idx)


def _asst(
    idx: int, text: str = "ok", tool_calls: int = 0, has_error: bool = False
) -> ConversationTurn:
    return ConversationTurn(
        role="assistant",
        text=text,
        timestamp="",
        turn_index=idx,
        tool_calls=tool_calls,
        has_error=has_error,
    )


class TestDetectSessionType:
    def test_debugging_high_error_rate(self):
        """Sessions with >30% assistant errors -> debugging."""
        turns = [
            _user(0, "fix the auth bug"),
            _asst(1, "error: TypeError", has_error=True),
            _user(2, "try using optional chaining"),
            _asst(3, "error: still fails", has_error=True),
            _user(4, "check the null guard"),
            _asst(5, "fixed"),
        ]
        conv = _make_conv(turns)
        assert detect_session_type(conv) == SessionType.DEBUGGING

    def test_implementation_high_tool_trigger(self):
        """Sessions with high tool usage + long user turns -> implementation."""
        turns = [
            _user(
                0,
                "Implement the user authentication module with JWT tokens, "
                "bcrypt password hashing, and session management. " * 3,
            ),
            _asst(1, "done", tool_calls=8),
            _user(
                2,
                "Now add the middleware for route protection. "
                "Check the token expiry and refresh logic. " * 3,
            ),
            _asst(3, "done", tool_calls=6),
            _user(
                4,
                "Add tests for the auth module covering login, logout, "
                "and token refresh flows. " * 3,
            ),
            _asst(5, "done", tool_calls=5),
        ]
        conv = _make_conv(turns)
        assert detect_session_type(conv) == SessionType.IMPLEMENTATION

    def test_exploratory_high_semantic_shift(self):
        """Sessions with many topic changes + questions -> exploratory."""
        turns = [
            _user(0, "how does the auth module work?"),
            _asst(1, "it uses JWT"),
            _user(2, "what about the database schema?"),
            _asst(3, "it uses postgres"),
            _user(4, "how is caching handled?"),
            _asst(5, "redis"),
            _user(6, "what CI pipeline do we use?"),
            _asst(7, "github actions"),
        ]
        conv = _make_conv(turns)
        result = detect_session_type(conv)
        assert result == SessionType.EXPLORATORY

    def test_review_high_confirmation_ratio(self):
        """Sessions with mostly confirmations + low tool usage -> review."""
        turns = [
            _user(0, "looks good"),
            _asst(1, "anything else?"),
            _user(2, "yes"),
            _asst(3, "ok"),
            _user(4, "ok"),
            _asst(5, "done"),
            _user(6, "good"),
            _asst(7, "next?"),
            _user(8, "fine"),
            _asst(9, "ok"),
        ]
        conv = _make_conv(turns)
        assert detect_session_type(conv) == SessionType.REVIEW

    def test_ambiguous_returns_none(self):
        """Mixed sessions return None (use default weights)."""
        turns = [
            _user(0, "add a feature"),
            _asst(1, "ok", tool_calls=2),
            _user(2, "fix that bug"),
            _asst(3, "error", has_error=True),
            _user(4, "what does this do?"),
            _asst(5, "it does X"),
            _user(6, "update the readme"),
            _asst(7, "done"),
        ]
        conv = _make_conv(turns)
        # error_rate=1/4=0.25 (<0.30), tool_trigger_rate=1/4=0.25 (<0.40)
        # question_ratio low, confirmation_ratio low -> None
        assert detect_session_type(conv) is None

    def test_high_questions_low_shift_not_exploratory(self):
        """Questions about the same topic should NOT be exploratory."""
        turns = [
            _user(0, "how does auth work?"),
            _asst(1, "it uses JWT"),
            _user(2, "how does auth handle refresh?"),
            _asst(3, "it rotates tokens"),
            _user(4, "how does auth handle expiry?"),
            _asst(5, "it checks timestamps"),
        ]
        conv = _make_conv(turns)
        # High question_ratio but low semantic_shift -> NOT exploratory
        result = detect_session_type(conv)
        assert result != SessionType.EXPLORATORY

    def test_empty_conversation_returns_none(self):
        conv = _make_conv([])
        assert detect_session_type(conv) is None

    def test_user_only_turns_returns_none(self):
        """Adapters without assistant data -> None (graceful degradation)."""
        turns = [_user(i, f"prompt {i}") for i in range(10)]
        conv = _make_conv(turns)
        assert detect_session_type(conv) is None


class TestGetWeightsForType:
    def test_all_weights_sum_to_one(self):
        """Every session type's weights must sum to 1.0."""
        for st in SessionType:
            weights = get_weights_for_type(st)
            assert abs(sum(weights.values()) - 1.0) < 0.001, (
                f"{st.name} sums to {sum(weights.values())}"
            )

    def test_none_returns_default(self):
        from reprompt.core.distill import DEFAULT_WEIGHTS

        assert get_weights_for_type(None) == DEFAULT_WEIGHTS

    def test_debugging_boosts_error_recovery(self):
        w = get_weights_for_type(SessionType.DEBUGGING)
        from reprompt.core.distill import DEFAULT_WEIGHTS

        assert w["error_recovery"] > DEFAULT_WEIGHTS["error_recovery"]

    def test_implementation_boosts_tool_trigger(self):
        w = get_weights_for_type(SessionType.IMPLEMENTATION)
        from reprompt.core.distill import DEFAULT_WEIGHTS

        assert w["tool_trigger"] > DEFAULT_WEIGHTS["tool_trigger"]

    def test_has_six_keys(self):
        for st in SessionType:
            w = get_weights_for_type(st)
            assert len(w) == 6
            assert set(w.keys()) == {
                "position",
                "length",
                "tool_trigger",
                "error_recovery",
                "semantic_shift",
                "uniqueness",
            }
