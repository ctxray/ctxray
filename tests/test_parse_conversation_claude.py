"""Tests for ClaudeCodeAdapter.parse_conversation()."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from reprompt.adapters.claude_code import ClaudeCodeAdapter


def _write_jsonl(entries: list[dict]) -> Path:
    """Write entries to a temp JSONL file and return the path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for entry in entries:
        tmp.write(json.dumps(entry) + "\n")
    tmp.close()
    return Path(tmp.name)


SAMPLE_ENTRIES = [
    {
        "type": "user",
        "timestamp": "2026-03-23T10:00:00Z",
        "message": {"role": "user", "content": "Fix the auth bug in login.py"},
    },
    {
        "type": "assistant",
        "timestamp": "2026-03-23T10:00:05Z",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll fix the auth bug."},
                {
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": "src/auth/login.py"},
                },
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {
                        "file_path": "src/auth/login.py",
                        "old_string": "pass",
                        "new_string": "return True",
                    },
                },
            ],
        },
    },
    {
        "type": "user",
        "timestamp": "2026-03-23T10:01:00Z",
        "message": {"role": "user", "content": [{"type": "tool_result"}]},
    },
    {
        "type": "user",
        "timestamp": "2026-03-23T10:02:00Z",
        "message": {"role": "user", "content": "Now add tests"},
    },
    {
        "type": "assistant",
        "timestamp": "2026-03-23T10:02:05Z",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Error: file not found"},
            ],
        },
    },
    {
        "type": "user",
        "timestamp": "2026-03-23T10:03:00Z",
        "message": {"role": "user", "content": "The file is at tests/test_login.py"},
    },
    {
        "type": "progress",
        "timestamp": "2026-03-23T10:03:01Z",
    },
    {
        "type": "system",
        "timestamp": "2026-03-23T10:03:02Z",
        "message": {"role": "system", "content": "context injected"},
    },
]


def test_parse_conversation_returns_user_and_assistant():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    roles = [t.role for t in turns]
    assert "user" in roles
    assert "assistant" in roles


def test_parse_conversation_filters_progress_and_system():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    for t in turns:
        assert t.role in ("user", "assistant")


def test_parse_conversation_tool_calls_counted():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    assert assistant_turns[0].tool_calls == 2


def test_parse_conversation_tool_use_paths_extracted():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    # Edit path should be captured (Write/Edit only, not Read)
    assert "src/auth/login.py" in assistant_turns[0].tool_use_paths


def test_parse_conversation_error_detected():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    assert assistant_turns[1].has_error is True
    assert assistant_turns[0].has_error is False


def test_parse_conversation_turn_indices_sequential():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    for i, turn in enumerate(turns):
        assert turn.turn_index == i


def test_parse_conversation_timestamps_preserved():
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assert turns[0].timestamp == "2026-03-23T10:00:00Z"


def test_parse_conversation_tool_result_user_filtered():
    """User entries with only tool_result content should be filtered."""
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    user_texts = [t.text for t in turns if t.role == "user"]
    for text in user_texts:
        assert text.strip() != ""


def test_parse_conversation_empty_file():
    path = _write_jsonl([])
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assert turns == []


def test_parse_conversation_tool_names_extracted():
    """tool_names should contain the name of each tool_use block."""
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    assert assistant_turns[0].tool_names == ["Read", "Edit"]


def test_parse_conversation_tool_names_empty_for_text_only():
    """Assistant turn with only text should have empty tool_names."""
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    # Second assistant turn has only text (error), no tools
    assert assistant_turns[1].tool_names == []


def test_parse_conversation_error_text_captured():
    """error_text should contain the actual error message."""
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    assert assistant_turns[1].error_text == "Error: file not found"
    # Non-error turn should have empty error_text
    assert assistant_turns[0].error_text == ""


def test_parse_conversation_user_turns_no_tool_names():
    """User turns should always have empty tool_names and error_text."""
    path = _write_jsonl(SAMPLE_ENTRIES)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    user_turns = [t for t in turns if t.role == "user"]
    for t in user_turns:
        assert t.tool_names == []
        assert t.error_text == ""


def test_parse_conversation_multiple_tool_types():
    """Verify tool_names captures all tool types."""
    entries = [
        {
            "type": "user",
            "timestamp": "2026-03-23T10:00:00Z",
            "message": {"role": "user", "content": "Run the tests and fix failures"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-03-23T10:00:05Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Running tests now."},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "pytest tests/"}},
                    {"type": "tool_use", "name": "Grep", "input": {"pattern": "def test_"}},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "tests/foo.py"}},
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": "tests/bar.py", "content": "..."},
                    },
                ],
            },
        },
    ]
    path = _write_jsonl(entries)
    adapter = ClaudeCodeAdapter()
    turns = adapter.parse_conversation(path)
    assistant_turns = [t for t in turns if t.role == "assistant"]
    assert assistant_turns[0].tool_names == ["Bash", "Grep", "Read", "Write"]
    assert assistant_turns[0].tool_calls == 4
    # Write path should be captured
    assert "tests/bar.py" in assistant_turns[0].tool_use_paths
