"""Tests for BaseAdapter.parse_conversation() default implementation."""

from __future__ import annotations

from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.core.conversation import ConversationTurn
from reprompt.core.models import Prompt


class StubAdapter(BaseAdapter):
    """Minimal adapter for testing the default parse_conversation()."""

    name = "stub"
    default_session_path = "/tmp/stub"

    def detect_installed(self) -> bool:
        return True

    def parse_session(self, path: Path) -> list[Prompt]:
        return [
            Prompt(
                text="first prompt",
                source="stub",
                session_id="s1",
                timestamp="2026-01-01T00:00:00Z",
            ),
            Prompt(
                text="second prompt",
                source="stub",
                session_id="s1",
                timestamp="2026-01-01T00:01:00Z",
            ),
        ]


def test_default_parse_conversation_wraps_parse_session():
    adapter = StubAdapter()
    turns = adapter.parse_conversation(Path("/fake/path"))
    assert len(turns) == 2
    assert all(isinstance(t, ConversationTurn) for t in turns)
    assert turns[0].role == "user"
    assert turns[0].text == "first prompt"
    assert turns[0].turn_index == 0
    assert turns[1].turn_index == 1
    assert turns[1].timestamp == "2026-01-01T00:01:00Z"


def test_default_parse_conversation_empty():
    class EmptyAdapter(BaseAdapter):
        name = "empty"
        default_session_path = "/tmp/empty"

        def detect_installed(self) -> bool:
            return True

        def parse_session(self, path: Path) -> list[Prompt]:
            return []

    adapter = EmptyAdapter()
    turns = adapter.parse_conversation(Path("/fake"))
    assert turns == []
