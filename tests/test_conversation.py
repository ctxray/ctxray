"""Tests for conversation data model."""

from __future__ import annotations

from ctxray.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)


class TestConversationTurn:
    def test_basic_user_turn(self):
        turn = ConversationTurn(
            role="user",
            text="Fix the auth bug",
            timestamp="2026-03-23T10:00:00Z",
            turn_index=0,
        )
        assert turn.role == "user"
        assert turn.text == "Fix the auth bug"
        assert turn.turn_index == 0
        assert turn.tool_calls == 0
        assert turn.has_error is False
        assert turn.tool_use_paths == []
        assert turn.score is None
        assert turn.is_duplicate is False
        assert turn.importance == 0.0

    def test_assistant_turn_with_tool_calls(self):
        turn = ConversationTurn(
            role="assistant",
            text="I'll fix the auth bug...",
            timestamp="2026-03-23T10:00:05Z",
            turn_index=1,
            tool_calls=3,
            has_error=False,
            tool_use_paths=["src/auth.py", "tests/test_auth.py"],
        )
        assert turn.tool_calls == 3
        assert turn.tool_use_paths == ["src/auth.py", "tests/test_auth.py"]

    def test_turn_with_enrichment(self):
        turn = ConversationTurn(
            role="user",
            text="hello",
            timestamp="",
            turn_index=0,
            score=75.0,
            is_duplicate=True,
            importance=0.85,
        )
        assert turn.score == 75.0
        assert turn.is_duplicate is True
        assert turn.importance == 0.85


class TestConversation:
    def test_basic_conversation(self):
        turns = [
            ConversationTurn(role="user", text="hi", timestamp="", turn_index=0),
            ConversationTurn(role="assistant", text="hello", timestamp="", turn_index=1),
        ]
        conv = Conversation(
            session_id="abc123",
            source="claude-code",
            project="ctxray",
            turns=turns,
        )
        assert conv.session_id == "abc123"
        assert conv.source == "claude-code"
        assert len(conv.turns) == 2
        assert conv.start_time is None
        assert conv.duration_seconds is None

    def test_conversation_with_timing(self):
        conv = Conversation(
            session_id="abc",
            source="claude-code",
            project=None,
            turns=[],
            start_time="2026-03-23T10:00:00Z",
            end_time="2026-03-23T10:45:00Z",
            duration_seconds=2700,
        )
        assert conv.duration_seconds == 2700


class TestDistillStats:
    def test_defaults(self):
        stats = DistillStats()
        assert stats.total_turns == 0
        assert stats.kept_turns == 0
        assert stats.retention_ratio == 0.0
        assert stats.total_duration_seconds == 0

    def test_with_values(self):
        stats = DistillStats(
            total_turns=47,
            kept_turns=12,
            retention_ratio=0.26,
            total_duration_seconds=2700,
        )
        assert stats.retention_ratio == 0.26


class TestDistillResult:
    def test_basic_result(self):
        conv = Conversation(session_id="abc", source="claude-code", project=None, turns=[])
        result = DistillResult(
            conversation=conv,
            filtered_turns=[],
            threshold=0.3,
        )
        assert result.summary is None
        assert result.files_changed == []
        assert result.stats.total_turns == 0
