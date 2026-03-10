"""Tests for OpenClaw adapter."""
from __future__ import annotations

from pathlib import Path

from reprompt.adapters.openclaw import OpenClawAdapter


def test_detect_installed(tmp_path):
    (tmp_path / ".opencode" / "sessions").mkdir(parents=True)
    adapter = OpenClawAdapter(session_path=tmp_path / ".opencode" / "sessions")
    assert adapter.detect_installed()


def test_detect_not_installed(tmp_path):
    adapter = OpenClawAdapter(session_path=tmp_path / "nonexistent")
    assert not adapter.detect_installed()


def test_parse_session(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    assert len(prompts) >= 3
    assert all(p.source == "openclaw" for p in prompts)


def test_filters_noise(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    texts = [p.text for p in prompts]
    # Short/noise messages should be filtered
    for t in texts:
        assert len(t) >= 10


def test_filters_assistant_messages(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    # No assistant messages
    for p in prompts:
        assert "I'll implement" not in p.text


def test_prompts_have_timestamps(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    assert all(p.timestamp for p in prompts)


def test_prompts_have_session_id(fixtures_path):
    adapter = OpenClawAdapter()
    prompts = adapter.parse_session(fixtures_path / "openclaw_session.jsonl")
    # Session ID from the JSONL data
    assert all(p.session_id == "sess_123" for p in prompts)


def test_extracts_project_from_path():
    adapter = OpenClawAdapter()
    name = adapter._project_from_path(
        "/Users/chris/.opencode/sessions/my-project/sess.jsonl"
    )
    assert name == "my-project"


def test_name_attribute():
    adapter = OpenClawAdapter()
    assert adapter.name == "openclaw"
