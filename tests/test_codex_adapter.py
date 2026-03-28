"""Tests for Codex CLI adapter."""

from __future__ import annotations

import json
from pathlib import Path

from reprompt.adapters.codex import CodexAdapter


def _write_rollout(
    tmp_path: Path,
    lines: list[dict],
    name: str = "rollout-2026-03-28T10-00-00-abcd1234-5678-9abc-def0-123456789abc.jsonl",
) -> Path:
    """Write a Codex rollout JSONL file in the expected directory structure."""
    session_dir = tmp_path / "sessions" / "2026" / "03" / "28"
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / name
    with open(path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return path


SAMPLE_SESSION = [
    {
        "timestamp": "2026-03-28T10:00:00Z",
        "type": "session_meta",
        "payload": {
            "id": "abcd1234-5678-9abc-def0-123456789abc",
            "cwd": "/Users/chris/projects/myapp",
            "cli_version": "0.1.2506131",
        },
    },
    {
        "timestamp": "2026-03-28T10:00:10Z",
        "type": "event_msg",
        "payload": {
            "type": "user_message",
            "message": "Fix the authentication bug in login.py",
        },
    },
    {
        "timestamp": "2026-03-28T10:00:15Z",
        "type": "event_msg",
        "payload": {
            "type": "agent_message",
            "message": "I'll fix the auth bug. Let me read the file first.",
        },
    },
    {
        "timestamp": "2026-03-28T10:00:16Z",
        "type": "response_item",
        "payload": {
            "type": "local_shell_call",
            "call_id": "call_001",
            "status": "completed",
            "action": {"type": "exec", "command": ["cat", "login.py"]},
        },
    },
    {
        "timestamp": "2026-03-28T10:00:17Z",
        "type": "event_msg",
        "payload": {
            "type": "exec_command_end",
            "call_id": "call_001",
            "command": ["cat", "login.py"],
            "exit_code": 0,
            "aggregated_output": "def login(user, pwd): ...",
            "duration": "0.1s",
        },
    },
    {
        "timestamp": "2026-03-28T10:00:18Z",
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "apply_patch",
            "arguments": '{"patch": "..."}',
            "call_id": "call_002",
        },
    },
    {
        "timestamp": "2026-03-28T10:01:00Z",
        "type": "event_msg",
        "payload": {
            "type": "user_message",
            "message": "Now run the tests to make sure it works",
        },
    },
    {
        "timestamp": "2026-03-28T10:01:05Z",
        "type": "event_msg",
        "payload": {
            "type": "agent_message",
            "message": "Running the test suite.",
        },
    },
    {
        "timestamp": "2026-03-28T10:01:06Z",
        "type": "response_item",
        "payload": {
            "type": "local_shell_call",
            "call_id": "call_003",
            "status": "completed",
            "action": {"type": "exec", "command": ["pytest", "tests/test_login.py"]},
        },
    },
    {
        "timestamp": "2026-03-28T10:01:10Z",
        "type": "event_msg",
        "payload": {
            "type": "exec_command_end",
            "call_id": "call_003",
            "command": ["pytest", "tests/test_login.py"],
            "exit_code": 1,
            "aggregated_output": "FAILED test_login.py::test_auth - AssertionError",
            "duration": "3.5s",
        },
    },
    {
        "timestamp": "2026-03-28T10:01:11Z",
        "type": "event_msg",
        "payload": {
            "type": "error",
            "message": "Command failed with exit code 1",
        },
    },
]


# ---------------------------------------------------------------------------
# Session discovery
# ---------------------------------------------------------------------------


class TestSessionDiscovery:
    def test_discover_sessions(self, tmp_path):
        _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 1
        assert "rollout-" in sessions[0].name

    def test_discover_no_sessions(self, tmp_path):
        adapter = CodexAdapter(codex_home=tmp_path)
        assert adapter.discover_sessions() == []

    def test_discover_multiple_sessions(self, tmp_path):
        _write_rollout(tmp_path, SAMPLE_SESSION, "rollout-2026-03-28T10-00-00-aaaa.jsonl")
        _write_rollout(tmp_path, SAMPLE_SESSION, "rollout-2026-03-28T11-00-00-bbbb.jsonl")
        adapter = CodexAdapter(codex_home=tmp_path)
        sessions = adapter.discover_sessions()
        assert len(sessions) == 2

    def test_detect_installed(self, tmp_path):
        adapter = CodexAdapter(codex_home=tmp_path)
        assert adapter.detect_installed() is False

        _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter2 = CodexAdapter(codex_home=tmp_path)
        assert adapter2.detect_installed() is True


# ---------------------------------------------------------------------------
# Prompt parsing (parse_session)
# ---------------------------------------------------------------------------


class TestParseSession:
    def test_extracts_user_prompts(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        prompts = adapter.parse_session(path)
        assert len(prompts) == 2
        assert "authentication bug" in prompts[0].text
        assert "run the tests" in prompts[1].text

    def test_source_is_codex(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        prompts = adapter.parse_session(path)
        assert all(p.source == "codex" for p in prompts)

    def test_project_from_cwd(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        prompts = adapter.parse_session(path)
        assert prompts[0].project == "myapp"

    def test_filters_short_messages(self, tmp_path):
        lines = [
            {
                "timestamp": "",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "ok"},
            },
            {
                "timestamp": "",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "yes"},
            },
        ]
        path = _write_rollout(tmp_path, lines)
        adapter = CodexAdapter(codex_home=tmp_path)
        prompts = adapter.parse_session(path)
        assert len(prompts) == 0

    def test_empty_file(self, tmp_path):
        path = _write_rollout(tmp_path, [])
        adapter = CodexAdapter(codex_home=tmp_path)
        prompts = adapter.parse_session(path)
        assert prompts == []

    def test_timestamps_preserved(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        prompts = adapter.parse_session(path)
        assert prompts[0].timestamp == "2026-03-28T10:00:10Z"


# ---------------------------------------------------------------------------
# Conversation parsing (parse_conversation)
# ---------------------------------------------------------------------------


class TestParseConversation:
    def test_returns_user_and_assistant_turns(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        roles = [t.role for t in turns]
        assert "user" in roles
        assert "assistant" in roles

    def test_tool_names_extracted(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        asst_turns = [t for t in turns if t.role == "assistant"]
        # First assistant turn: cat + apply_patch
        assert "cat" in asst_turns[0].tool_names
        assert "apply_patch" in asst_turns[0].tool_names
        assert asst_turns[0].tool_calls == 2

    def test_error_detected_from_exit_code(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        asst_turns = [t for t in turns if t.role == "assistant"]
        # Second assistant turn: pytest fails
        assert asst_turns[1].has_error is True
        assert "FAILED" in asst_turns[1].error_text

    def test_clean_turn_no_error(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        asst_turns = [t for t in turns if t.role == "assistant"]
        # First assistant turn: cat succeeds
        assert asst_turns[0].has_error is False

    def test_tool_paths_from_commands(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        asst_turns = [t for t in turns if t.role == "assistant"]
        # Second assistant turn: pytest tests/test_login.py
        assert "tests/test_login.py" in asst_turns[1].tool_use_paths

    def test_turn_indices_sequential(self, tmp_path):
        path = _write_rollout(tmp_path, SAMPLE_SESSION)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        for i, turn in enumerate(turns):
            assert turn.turn_index == i

    def test_empty_file(self, tmp_path):
        path = _write_rollout(tmp_path, [])
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        assert turns == []

    def test_user_only_session(self, tmp_path):
        lines = [
            {
                "timestamp": "T1",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": "Hello, please help me with something",
                },
            },
        ]
        path = _write_rollout(tmp_path, lines)
        adapter = CodexAdapter(codex_home=tmp_path)
        turns = adapter.parse_conversation(path)
        assert len(turns) == 1
        assert turns[0].role == "user"


# ---------------------------------------------------------------------------
# Session ID extraction
# ---------------------------------------------------------------------------


class TestSessionId:
    def test_extracts_uuid_from_filename(self):
        adapter = CodexAdapter()
        path = Path("rollout-2026-03-28T10-00-00-abcd1234-5678-9abc-def0-123456789abc.jsonl")
        sid = adapter._session_id_from_path(path)
        assert sid == "abcd1234-5678-9abc-def0-123456789abc"

    def test_short_filename(self):
        adapter = CodexAdapter()
        path = Path("rollout-short.jsonl")
        sid = adapter._session_id_from_path(path)
        assert sid == "short"
