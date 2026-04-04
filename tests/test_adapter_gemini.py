"""Tests for Gemini CLI adapter."""

from __future__ import annotations

from ctxray.adapters.gemini import GeminiAdapter


def test_detect_installed(tmp_path):
    chats = tmp_path / "tmp" / "abc123" / "chats"
    chats.mkdir(parents=True)
    (chats / "session-2026-03-10T14-23-a1b2c3d4.json").write_text("{}")
    adapter = GeminiAdapter(gemini_home=tmp_path)
    assert adapter.detect_installed()


def test_detect_not_installed(tmp_path):
    adapter = GeminiAdapter(gemini_home=tmp_path)
    assert not adapter.detect_installed()


def test_parse_session(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    # Should extract only user messages, filtering short ones
    assert len(prompts) == 3
    assert all(p.source == "gemini" for p in prompts)


def test_extracts_user_messages(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    texts = [p.text for p in prompts]
    assert "fix the authentication bug in login.py" in texts
    assert "add unit tests for the user service with edge cases for empty email" in texts
    assert "refactor the database connection pool to use async context managers" in texts


def test_skips_ai_responses(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "I'll fix" not in t
        assert "I'll create" not in t


def test_skips_system_messages(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    texts = [p.text for p in prompts]
    for t in texts:
        assert "Applied edit" not in t
        assert "Failed to apply" not in t


def test_skips_short_messages(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    texts = [p.text for p in prompts]
    assert "ok" not in texts


def test_handles_list_content(fixtures_path):
    """Content can be a list of text parts (PartListUnion)."""
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    texts = [p.text for p in prompts]
    assert "refactor the database connection pool to use async context managers" in texts


def test_per_message_timestamps(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    assert prompts[0].timestamp == "2026-03-10T14:23:01.000Z"
    assert prompts[1].timestamp == "2026-03-10T14:30:00.000Z"


def test_session_id_from_file(fixtures_path):
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(fixtures_path / "gemini_session.json")
    # Session ID comes from the JSON sessionId field
    assert all(p.session_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890" for p in prompts)


def test_discover_sessions(tmp_path):
    proj1 = tmp_path / "tmp" / "hash1" / "chats"
    proj1.mkdir(parents=True)
    (proj1 / "session-2026-03-10T14-23-aaaa.json").write_text('{"messages":[]}')

    proj2 = tmp_path / "tmp" / "hash2" / "chats"
    proj2.mkdir(parents=True)
    (proj2 / "session-2026-03-11T09-00-bbbb.json").write_text('{"messages":[]}')

    adapter = GeminiAdapter(gemini_home=tmp_path)
    sessions = adapter.discover_sessions()
    assert len(sessions) == 2
    assert all(s.suffix == ".json" for s in sessions)


def test_empty_file(tmp_path):
    empty = tmp_path / "session.json"
    empty.write_text("{}")
    adapter = GeminiAdapter()
    prompts = adapter.parse_session(empty)
    assert prompts == []
