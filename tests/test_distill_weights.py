"""Tests for per-signal scores and weights override."""

from __future__ import annotations

from ctxray.core.conversation import Conversation, ConversationTurn
from ctxray.core.distill import DEFAULT_WEIGHTS, distill_conversation


def _make_conv(user_texts: list[str], assistant_texts: list[str] | None = None) -> Conversation:
    """Build a Conversation from interleaved user/assistant text lists."""
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


class TestSignalScores:
    def test_signal_scores_populated(self):
        """After distill, each user turn should have all 6 signal scores."""
        conv = _make_conv(["Fix the bug", "Add tests", "Deploy"])
        result = distill_conversation(conv, threshold=0.0)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        for turn in user_turns:
            assert len(turn.signal_scores) == 6
            expected_keys = {
                "position",
                "length",
                "tool_trigger",
                "error_recovery",
                "semantic_shift",
                "uniqueness",
            }
            assert set(turn.signal_scores.keys()) == expected_keys

    def test_signal_scores_values_between_0_and_1(self):
        conv = _make_conv(["Do X", "Do Y", "Do Z"])
        result = distill_conversation(conv, threshold=0.0)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        for turn in user_turns:
            for key, val in turn.signal_scores.items():
                assert 0.0 <= val <= 1.0, f"{key}={val} out of range"

    def test_first_turn_has_position_1(self):
        conv = _make_conv(["First", "Second", "Third"])
        result = distill_conversation(conv, threshold=0.0)
        first_user = [t for t in result.conversation.turns if t.role == "user"][0]
        assert first_user.signal_scores["position"] == 1.0


class TestDefaultWeights:
    def test_default_weights_exist(self):
        assert isinstance(DEFAULT_WEIGHTS, dict)
        assert len(DEFAULT_WEIGHTS) == 6

    def test_default_weights_sum_to_1(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.01


class TestWeightsOverride:
    def test_custom_weights_change_importance(self):
        """Overriding semantic_shift to 1.0 (others 0) should rank by shift only."""
        conv = _make_conv(
            [
                "Fix the auth bug",
                "Now let's do something completely different about databases",
                "Fix another auth bug",
            ]
        )
        zero_weights = {k: 0.0 for k in DEFAULT_WEIGHTS}
        zero_weights["semantic_shift"] = 1.0
        result = distill_conversation(conv, threshold=0.0, weights=zero_weights)
        user_turns = [t for t in result.conversation.turns if t.role == "user"]
        # Turn with highest semantic shift should have highest importance
        importances = [t.importance for t in user_turns]
        assert user_turns[1].importance == max(importances)

    def test_none_weights_uses_defaults(self):
        conv = _make_conv(["Hello", "World"])
        result_default = distill_conversation(conv, threshold=0.0)
        result_none = distill_conversation(conv, threshold=0.0, weights=None)
        user_default = [t for t in result_default.conversation.turns if t.role == "user"]
        user_none = [t for t in result_none.conversation.turns if t.role == "user"]
        for d, n in zip(user_default, user_none):
            assert abs(d.importance - n.importance) < 0.001
