"""Tests for Cline adapter."""

from __future__ import annotations

import json

from reprompt.adapters.cline import ClineAdapter


def test_detect_installed(tmp_path):
    tasks = tmp_path / "saoudrizwan.claude-dev" / "tasks" / "12345"
    tasks.mkdir(parents=True)
    (tasks / "api_conversation_history.json").write_text("[]")
    adapter = ClineAdapter(storage_paths=[tmp_path / "saoudrizwan.claude-dev"])
    assert adapter.detect_installed()


def test_detect_not_installed(tmp_path):
    adapter = ClineAdapter(storage_paths=[tmp_path / "nonexistent"])
    assert not adapter.detect_installed()


def test_parse_session(fixtures_path):
    adapter = ClineAdapter()
    prompts = adapter.parse_session(fixtures_path / "cline_task" / "api_conversation_history.json")
    # 3 real user prompts (not tool_result, not short)
    assert len(prompts) == 3
    assert all(p.source == "cline" for p in prompts)


def test_extracts_user_messages(fixtures_path):
    adapter = ClineAdapter()
    prompts = adapter.parse_session(fixtures_path / "cline_task" / "api_conversation_history.json")
    texts = [p.text for p in prompts]
    assert "Fix the authentication bug in auth.py — login returns 401 for valid credentials" in texts
    assert "Now add unit tests for the user service with pytest fixtures" in texts
    assert "refactor database pool to use async context managers" in texts


def test_skips_tool_results(fixtures_path):
    """Messages with tool_result content should be filtered."""
    adapter = ClineAdapter()
    prompts = adapter.parse_session(fixtures_path / "cline_task" / "api_conversation_history.json")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "def login" not in t
        assert "File written" not in t


def test_skips_assistant_messages(fixtures_path):
    adapter = ClineAdapter()
    prompts = adapter.parse_session(fixtures_path / "cline_task" / "api_conversation_history.json")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "I'll fix" not in t
        assert "I see the issue" not in t


def test_skips_short_messages(fixtures_path):
    adapter = ClineAdapter()
    prompts = adapter.parse_session(fixtures_path / "cline_task" / "api_conversation_history.json")
    texts = [p.text for p in prompts]
    assert "ok" not in texts


def test_handles_mixed_content_blocks(fixtures_path):
    """Content with text + image blocks should extract only text."""
    adapter = ClineAdapter()
    prompts = adapter.parse_session(fixtures_path / "cline_task" / "api_conversation_history.json")
    texts = [p.text for p in prompts]
    assert "refactor database pool to use async context managers" in texts


def test_project_from_path():
    adapter = ClineAdapter()
    project = adapter._project_from_path(
        "/Users/chris/Library/Application Support/Code/User/globalStorage/"
        "saoudrizwan.claude-dev/tasks/1710000000/api_conversation_history.json"
    )
    assert project == "1710000000"


def test_discover_sessions(tmp_path):
    storage = tmp_path / "saoudrizwan.claude-dev"
    for task_id in ["111", "222"]:
        task_dir = storage / "tasks" / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "api_conversation_history.json").write_text("[]")

    adapter = ClineAdapter(storage_paths=[storage])
    sessions = adapter.discover_sessions()
    assert len(sessions) == 2


def test_empty_file(tmp_path):
    empty = tmp_path / "api_conversation_history.json"
    empty.write_text("[]")
    adapter = ClineAdapter()
    prompts = adapter.parse_session(empty)
    assert prompts == []
