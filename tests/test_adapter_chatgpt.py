"""Tests for ChatGPT adapter."""

from __future__ import annotations

from pathlib import Path

from reprompt.adapters.chatgpt import ChatGPTAdapter


def test_parse_extracts_user_messages(fixtures_path: Path) -> None:
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(fixtures_path / "chatgpt_conversations.json")
    texts = [p.text for p in prompts]
    assert len(texts) == 4
    assert "Explain how Python async/await works with a simple example" in texts
    assert (
        "Suggest three quick dinner recipes using chicken and rice that take under 30 minutes"
        in texts
    )


def test_skips_system_and_assistant(fixtures_path: Path) -> None:
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(fixtures_path / "chatgpt_conversations.json")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "You are ChatGPT" not in t
        assert "Python's async/await is built on coroutines" not in t
        assert "Here are three quick chicken and rice" not in t


def test_source_is_chatgpt_export(fixtures_path: Path) -> None:
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(fixtures_path / "chatgpt_conversations.json")
    assert all(p.source == "chatgpt-export" for p in prompts)


def test_session_id_from_conversation_title(fixtures_path: Path) -> None:
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(fixtures_path / "chatgpt_conversations.json")
    # First two prompts from "Python async help", next two from "Recipe ideas"
    assert prompts[0].session_id == prompts[1].session_id
    assert prompts[2].session_id == prompts[3].session_id
    assert prompts[0].session_id != prompts[2].session_id


def test_timestamps_from_create_time(fixtures_path: Path) -> None:
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(fixtures_path / "chatgpt_conversations.json")
    # All prompts should have a timestamp string
    assert all(p.timestamp for p in prompts)


def test_project_from_conversation_title(fixtures_path: Path) -> None:
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(fixtures_path / "chatgpt_conversations.json")
    assert prompts[0].project == "Python async help"
    assert prompts[2].project == "Recipe ideas"


def test_handles_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.json"
    f.write_text("[]")
    adapter = ChatGPTAdapter()
    assert adapter.parse_session(f) == []


def test_handles_missing_message_node(tmp_path: Path) -> None:
    """Nodes with message=null (root nodes) should be skipped."""
    import json

    data = [
        {
            "title": "test",
            "create_time": 1.0,
            "update_time": 1.0,
            "mapping": {"root": {"id": "root", "parent": None, "children": [], "message": None}},
        }
    ]
    f = tmp_path / "conv.json"
    f.write_text(json.dumps(data))
    adapter = ChatGPTAdapter()
    assert adapter.parse_session(f) == []


def test_handles_multipart_content(tmp_path: Path) -> None:
    """Content parts should be joined."""
    import json

    data = [
        {
            "title": "test",
            "create_time": 1.0,
            "update_time": 1.0,
            "mapping": {
                "root": {"id": "root", "parent": None, "children": ["u1"], "message": None},
                "u1": {
                    "id": "u1",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "u1",
                        "author": {"role": "user"},
                        "create_time": 1.0,
                        "content": {"content_type": "text", "parts": ["Part one. ", "Part two."]},
                    },
                },
            },
        }
    ]
    f = tmp_path / "conv.json"
    f.write_text(json.dumps(data))
    adapter = ChatGPTAdapter()
    prompts = adapter.parse_session(f)
    assert len(prompts) == 1
    assert prompts[0].text == "Part one. Part two."


def test_detect_installed_false() -> None:
    adapter = ChatGPTAdapter()
    assert not adapter.detect_installed()
