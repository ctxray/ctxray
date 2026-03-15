"""Tests for Claude.ai chat export adapter."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from reprompt.adapters.claude_chat import ClaudeChatAdapter


def test_parse_extracts_human_messages(fixtures_path: Path) -> None:
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_chat_export.json")
    texts = [p.text for p in prompts]
    assert len(texts) == 4
    assert (
        "Explain quantum computing in simple terms that a high school student would understand"
        in texts
    )
    assert (
        "Plan a 5-day itinerary for visiting Kyoto in cherry blossom season with a moderate budget"
        in texts
    )


def test_skips_assistant_messages(fixtures_path: Path) -> None:
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_chat_export.json")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "Quantum computing uses quantum bits" not in t
        assert "Here is your Kyoto itinerary" not in t


def test_source_is_claude_chat_export(fixtures_path: Path) -> None:
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_chat_export.json")
    assert all(p.source == "claude-chat-export" for p in prompts)


def test_session_id_per_conversation(fixtures_path: Path) -> None:
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_chat_export.json")
    # First 2 from conv-001, next 2 from conv-002
    assert prompts[0].session_id == prompts[1].session_id
    assert prompts[2].session_id == prompts[3].session_id
    assert prompts[0].session_id != prompts[2].session_id


def test_project_from_conversation_name(fixtures_path: Path) -> None:
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_chat_export.json")
    assert prompts[0].project == "Explain quantum computing"
    assert prompts[2].project == "Travel planning"


def test_timestamps_from_created_at(fixtures_path: Path) -> None:
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_chat_export.json")
    assert all(p.timestamp for p in prompts)
    assert "2026-03-01" in prompts[0].timestamp


def test_handles_zip_file(tmp_path: Path) -> None:
    """Claude.ai exports come as ZIP files -- adapter should handle both."""
    conversations = [
        {
            "uuid": "z1",
            "name": "Zip test",
            "created_at": "2026-03-01T10:00:00Z",
            "updated_at": "2026-03-01T10:00:00Z",
            "chat_messages": [
                {
                    "uuid": "zm1",
                    "sender": "human",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello from a zip file, what can you help me with?",
                        }
                    ],
                    "created_at": "2026-03-01T10:00:00Z",
                    "updated_at": "2026-03-01T10:00:00Z",
                    "index": 0,
                    "truncated": False,
                }
            ],
        }
    ]
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("conversations.json", json.dumps(conversations))
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(zip_path)
    assert len(prompts) == 1
    assert "Hello from a zip file" in prompts[0].text


def test_handles_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.json"
    f.write_text("[]")
    adapter = ClaudeChatAdapter()
    assert adapter.parse_session(f) == []


def test_handles_single_conversation_format(tmp_path: Path) -> None:
    """Claude.ai can also export a single conversation (not wrapped in array)."""
    data = {
        "uuid": "single-001",
        "name": "Single export",
        "created_at": "2026-03-01T10:00:00Z",
        "updated_at": "2026-03-01T10:00:00Z",
        "chat_messages": [
            {
                "uuid": "sm1",
                "sender": "human",
                "content": [
                    {
                        "type": "text",
                        "text": "This is a single conversation export for testing purposes",
                    }
                ],
                "created_at": "2026-03-01T10:00:00Z",
                "updated_at": "2026-03-01T10:00:00Z",
                "index": 0,
                "truncated": False,
            }
        ],
    }
    f = tmp_path / "single.json"
    f.write_text(json.dumps(data))
    adapter = ClaudeChatAdapter()
    prompts = adapter.parse_session(f)
    assert len(prompts) == 1


def test_detect_installed_false() -> None:
    adapter = ClaudeChatAdapter()
    assert not adapter.detect_installed()
