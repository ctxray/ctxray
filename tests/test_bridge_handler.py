"""Tests for Native Messaging message handler."""

from __future__ import annotations

from pathlib import Path

from reprompt.bridge.handler import handle_message
from reprompt.storage.db import PromptDB


def test_handle_ping(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "ping"}, db)
    assert response["type"] == "pong"
    assert "version" in response


def test_handle_sync_prompts(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "Explain how async/await works in Python",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:00:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python async",
            },
            {
                "text": "Show me a simple example of asyncio.gather",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:01:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python async",
            },
        ],
    }
    response = handle_message(msg, db)
    assert response["type"] == "sync_result"
    assert response["received"] == 2
    assert response["new_stored"] == 2
    assert response["duplicates"] == 0


def test_handle_sync_dedup(tmp_path: Path) -> None:
    """Second sync of same prompts should report duplicates."""
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "Explain how async/await works in Python",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:00:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python async",
            },
        ],
    }
    handle_message(msg, db)
    response = handle_message(msg, db)
    assert response["new_stored"] == 0
    assert response["duplicates"] == 1


def test_handle_sync_filters_short(tmp_path: Path) -> None:
    """Short/noise prompts should be filtered out."""
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "ok",
                "source": "chatgpt-ext",
                "timestamp": "",
                "conversation_id": "c1",
                "conversation_title": "t",
            },
            {
                "text": "yes",
                "source": "chatgpt-ext",
                "timestamp": "",
                "conversation_id": "c1",
                "conversation_title": "t",
            },
        ],
    }
    response = handle_message(msg, db)
    assert response["received"] == 2
    assert response["new_stored"] == 0


def test_handle_get_status(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    # Insert a prompt so stats are non-empty
    db.insert_prompt(
        "Test prompt for status check", source="chatgpt-ext", project="test", session_id="s1"
    )
    response = handle_message({"type": "get_status"}, db)
    assert response["type"] == "status"
    assert response["total_prompts"] >= 1
    assert "version" in response


def test_handle_unknown_type(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "unknown_xyz"}, db)
    assert response["type"] == "error"
    assert "unknown" in response["message"].lower()


def test_handle_empty_sync(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "sync_prompts", "prompts": []}, db)
    assert response["type"] == "sync_result"
    assert response["received"] == 0
    assert response["new_stored"] == 0
