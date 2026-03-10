"""Tests for core data models."""
from reprompt.core.models import Prompt


def test_prompt_auto_hash():
    p = Prompt(text="hello world", source="claude-code", session_id="abc")
    assert p.hash
    assert len(p.hash) == 64


def test_prompt_hash_deterministic():
    p1 = Prompt(text="hello world", source="claude-code", session_id="abc")
    p2 = Prompt(text="hello world", source="claude-code", session_id="def")
    assert p1.hash == p2.hash


def test_prompt_strips_whitespace():
    p = Prompt(text="  hello  ", source="test", session_id="x")
    assert p.char_count == 5


def test_prompt_from_dict():
    d = {"text": "test prompt", "source": "claude-code", "session_id": "s1",
         "project": "myproject", "timestamp": "2026-01-01T00:00:00Z"}
    p = Prompt(**d)
    assert p.project == "myproject"
