"""Tests for Aider adapter."""

from __future__ import annotations

from reprompt.adapters.aider import AiderAdapter


def test_detect_installed(tmp_path):
    (tmp_path / "myproject").mkdir()
    (tmp_path / "myproject" / ".aider.chat.history.md").write_text("# aider chat\n")
    adapter = AiderAdapter(search_roots=[tmp_path])
    assert adapter.detect_installed()


def test_detect_not_installed(tmp_path):
    adapter = AiderAdapter(search_roots=[tmp_path])
    assert not adapter.detect_installed()


def test_parse_session(fixtures_path):
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    # Should extract only user messages (#### lines)
    assert len(prompts) == 3
    assert all(p.source == "aider" for p in prompts)


def test_extracts_user_messages(fixtures_path):
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    texts = [p.text for p in prompts]
    assert "fix the authentication bug in login.py" in texts
    assert "add unit tests for the user service" in texts
    assert "refactor database connection pool to use async context managers" in texts


def test_skips_ai_responses(fixtures_path):
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "I'll fix" not in t
        assert "I'll create" not in t
        assert "I'll refactor" not in t


def test_skips_tool_output(fixtures_path):
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "Applied edit" not in t
        assert "Commit" not in t
        assert "Add db/pool.py" not in t


def test_skips_short_messages(fixtures_path):
    """Short messages like 'ok', 'y' should be filtered out."""
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    texts = [p.text for p in prompts]
    assert "ok" not in texts
    assert "y" not in texts


def test_session_boundary_detection(fixtures_path):
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    # First two prompts from session 1, third from session 2
    assert prompts[0].session_id == "2026-03-10T14-23-01"
    assert prompts[1].session_id == "2026-03-10T14-23-01"
    assert prompts[2].session_id == "2026-03-11T09-15-30"


def test_timestamps_from_session_header(fixtures_path):
    adapter = AiderAdapter()
    prompts = adapter.parse_session(fixtures_path / "aider_chat_history.md")
    assert prompts[0].timestamp == "2026-03-10 14:23:01"
    assert prompts[2].timestamp == "2026-03-11 09:15:30"


def test_project_from_path():
    adapter = AiderAdapter()
    # Test the project extraction helper
    project = adapter._project_from_path("/Users/chris/projects/myapp/.aider.chat.history.md")
    assert project == "myapp"


def test_empty_file(tmp_path):
    empty = tmp_path / ".aider.chat.history.md"
    empty.write_text("")
    adapter = AiderAdapter()
    prompts = adapter.parse_session(empty)
    assert prompts == []


def test_discover_sessions(tmp_path):
    """discover_sessions should find .aider.chat.history.md files recursively."""
    proj1 = tmp_path / "proj1"
    proj1.mkdir()
    (proj1 / ".aider.chat.history.md").write_text("# aider chat started at 2026-01-01 00:00:00\n")

    proj2 = tmp_path / "proj2"
    proj2.mkdir()
    (proj2 / ".aider.chat.history.md").write_text("# aider chat started at 2026-01-02 00:00:00\n")

    adapter = AiderAdapter(search_roots=[tmp_path])
    sessions = adapter.discover_sessions()
    assert len(sessions) == 2
    assert all(s.name == ".aider.chat.history.md" for s in sessions)
