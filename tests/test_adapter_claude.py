"""Tests for Claude Code adapter."""

from __future__ import annotations

from reprompt.adapters.claude_code import ClaudeCodeAdapter


def test_detect_installed(tmp_path):
    (tmp_path / ".claude" / "projects").mkdir(parents=True)
    adapter = ClaudeCodeAdapter(session_path=tmp_path / ".claude" / "projects")
    assert adapter.detect_installed()


def test_detect_not_installed(tmp_path):
    adapter = ClaudeCodeAdapter(session_path=tmp_path / "nonexistent")
    assert not adapter.detect_installed()


def test_parse_session(fixtures_path):
    adapter = ClaudeCodeAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_session.jsonl")
    assert len(prompts) >= 3
    assert all(p.source == "claude-code" for p in prompts)


def test_filters_noise(fixtures_path):
    adapter = ClaudeCodeAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_session.jsonl")
    texts = [p.text for p in prompts]
    # Short/noise messages should be filtered
    for t in texts:
        assert len(t) >= 10


def test_filters_assistant_messages(fixtures_path):
    adapter = ClaudeCodeAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_session.jsonl")
    # No assistant messages should be included
    for p in prompts:
        assert "I'll fix" not in p.text


def test_extracts_list_content(fixtures_path):
    adapter = ClaudeCodeAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_session.jsonl")
    texts = [p.text for p in prompts]
    # List-format content should be extracted properly
    assert any("payment module" in t for t in texts)


def test_extracts_project_name():
    adapter = ClaudeCodeAdapter()
    name = adapter._project_from_path(
        "/Users/chris/.claude/projects/-Users-chris-projects-myproject/abc.jsonl"
    )
    assert name == "myproject"


def test_extracts_project_name_nested():
    adapter = ClaudeCodeAdapter()
    name = adapter._project_from_path(
        "/Users/chris/.claude/projects/-Users-chris-projects-my-cool-app/abc.jsonl"
    )
    assert name == "my-cool-app"


def test_prompts_have_timestamps(fixtures_path):
    adapter = ClaudeCodeAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_session.jsonl")
    assert all(p.timestamp for p in prompts)


def test_prompts_have_session_id(fixtures_path):
    adapter = ClaudeCodeAdapter()
    prompts = adapter.parse_session(fixtures_path / "claude_session.jsonl")
    # Session ID should be derived from filename
    assert all(p.session_id == "claude_session" for p in prompts)


def test_skip_exact_messages():
    """Verify that exact-match noise words are filtered."""
    from reprompt.adapters.claude_code import should_keep_prompt

    assert not should_keep_prompt("ok")
    assert not should_keep_prompt("OK")
    assert not should_keep_prompt("yes")
    assert not should_keep_prompt("Done")
    assert not should_keep_prompt("sure")


def test_skip_prefix_messages():
    """Verify that prefix-match noise is filtered."""
    from reprompt.adapters.claude_code import should_keep_prompt

    assert not should_keep_prompt("<local-command>run test</local-command>")
    assert not should_keep_prompt("Tool loaded. Ready to use.")


def test_skip_short_messages():
    """Messages under 10 chars should be filtered."""
    from reprompt.adapters.claude_code import should_keep_prompt

    assert not should_keep_prompt("hi")
    assert not should_keep_prompt("123")


def test_keep_valid_messages():
    """Valid prompts should pass the filter."""
    from reprompt.adapters.claude_code import should_keep_prompt

    assert should_keep_prompt("fix the failing test in auth.py")
    assert should_keep_prompt("refactor the database connection pool")
