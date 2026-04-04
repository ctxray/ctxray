"""Tests for Claude Code adapter."""

from __future__ import annotations

from ctxray.adapters.claude_code import ClaudeCodeAdapter


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
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("ok")
    assert not should_keep_prompt("OK")
    assert not should_keep_prompt("yes")
    assert not should_keep_prompt("Done")
    assert not should_keep_prompt("sure")


def test_skip_prefix_messages():
    """Verify that prefix-match noise is filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("<local-command>run test</local-command>")
    assert not should_keep_prompt("Tool loaded. Ready to use.")


def test_skip_system_injections():
    """System-injected XML tags should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("<system-reminder>\nPreToolUse:Edit hook context")
    assert not should_keep_prompt("<task-notification>\n<task-id>abc123</task-id>")
    assert not should_keep_prompt("<ide_opened_file>The user opened file.py</ide_opened_file>")
    assert not should_keep_prompt(
        "<available-deferred-tools>\nSomeTool\n</available-deferred-tools>"
    )


def test_skip_short_messages():
    """Messages under 10 chars should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("hi")
    assert not should_keep_prompt("123")


def test_keep_valid_messages():
    """Valid prompts should pass the filter."""
    from ctxray.adapters.filters import should_keep_prompt

    assert should_keep_prompt("fix the failing test in auth.py")
    assert should_keep_prompt("refactor the database connection pool")


def test_skip_compact_continuation_messages():
    """Session compaction/continuation messages should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt(
        "This session is being continued from a previous conversation that ran out of context."
    )
    assert not should_keep_prompt(
        "This session is being continued from a previous conversation. Here is a summary."
    )


def test_skip_messages_with_system_noise():
    """Messages containing system noise substrings should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("The conversation ran out of context so we need to restart.")
    assert not should_keep_prompt(
        "Please process this <system-reminder>some reminder</system-reminder> data."
    )
    assert not should_keep_prompt("Summary: This is a compact session summary with details.")


def test_skip_continuation_instructions():
    """Instructions to continue conversations should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt(
        "Continue the conversation from where it left off without asking questions."
    )


def test_skip_tool_call_noise():
    """Tool call syntax injected as user messages should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("PreToolUse:Edit hook blocking error from command")
    assert not should_keep_prompt("PostToolUse:Edit hook additional context: [Edit context]")


def test_ide_prefix_stripped():
    """IDE-injected prefixes should be stripped, keeping the real prompt."""
    from ctxray.adapters.claude_code import _extract_text

    msg = {
        "content": (
            "<ide_opened_file>/path/to/file.py</ide_opened_file> "
            "How do I fix the auth bug in this file?"
        )
    }
    text = _extract_text(msg)
    assert text == "How do I fix the auth bug in this file?"
    assert "<ide_opened_file>" not in text


def test_ide_selection_prefix_stripped():
    """IDE selection blocks should be stripped, keeping the real prompt."""
    from ctxray.adapters.claude_code import _extract_text

    msg = {
        "content": (
            "<ide_selection>some selected code\nmore code</ide_selection>\n"
            "refactor this to use async/await"
        )
    }
    text = _extract_text(msg)
    assert text == "refactor this to use async/await"


def test_ide_only_message_kept_as_is():
    """If IDE prefix is the entire message, keep the raw text."""
    from ctxray.adapters.claude_code import _extract_text

    msg = {"content": "<ide_opened_file>/path/to/file.py</ide_opened_file>"}
    text = _extract_text(msg)
    # Raw text returned since stripping leaves nothing
    assert "ide_opened_file" in text


def test_skip_cli_commands():
    """CLI tool commands should be filtered — they're not real prompts."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("claude --continue")
    assert not should_keep_prompt("cursor open file.py")
    assert not should_keep_prompt("git status and check changes")
    assert not should_keep_prompt("npm install express")
    assert not should_keep_prompt("uv run pytest tests/ -v")
    assert not should_keep_prompt("ctxray scan --source claude-code")
    assert not should_keep_prompt("make test")
    assert not should_keep_prompt("cargo build --release")


def test_skip_slash_commands():
    """Slash commands should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("/help")
    assert not should_keep_prompt("/commit fix auth bug")
    assert not should_keep_prompt("/review-pr 123")


def test_keep_prompts_containing_tool_names():
    """Prompts that mention tools but are real questions should pass."""
    from ctxray.adapters.filters import should_keep_prompt

    assert should_keep_prompt("how do I configure cursor to use a custom model?")
    assert should_keep_prompt("explain the git rebase workflow for this branch")
    assert should_keep_prompt("why is npm install failing with this error?")


def test_skip_system_error_messages():
    """System error/status messages should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("Unknown skill: workflow")
    assert not should_keep_prompt("Unknown command: foobar something")
    assert not should_keep_prompt("Error: connection refused to localhost:8080")
    assert not should_keep_prompt("Warning: deprecated API usage detected")
    assert not should_keep_prompt("Permission denied: /etc/shadow")
    assert not should_keep_prompt("Command not found: some-tool")


def test_skip_extended_cli_commands():
    """Extended CLI commands from various tools should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("docker compose up -d")
    assert not should_keep_prompt("brew install python3")
    assert not should_keep_prompt("ssh user@host ls -la")
    assert not should_keep_prompt("cd ~/projects/myapp")
    assert not should_keep_prompt("sudo apt install build-essential")
    assert not should_keep_prompt("cline open task 12345")
    assert not should_keep_prompt("windsurf start project")


def test_skip_hook_noise():
    """Hook-related system messages should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("hook blocking error from some command")
    assert not should_keep_prompt("SessionStart:compact hook success: Success")


def test_skip_aider_status_messages():
    """Aider startup banners and status output should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("Aider v0.82.2")
    assert not should_keep_prompt("Main model: anthropic/claude-3.7-sonnet with diff edit format")
    assert not should_keep_prompt("Git repo: .git with 243 files")
    assert not should_keep_prompt("Repo-map: using 4096 tokens, auto refresh")
    assert not should_keep_prompt("Added src/main.py to the chat.")
    assert not should_keep_prompt("Removed src/old.py from the chat.")
    assert not should_keep_prompt("Tokens: 12,345 sent, 2,345 received. Cost: $0.04")
    assert not should_keep_prompt("Commit abc1234 Fix: resolve null pointer error")


def test_skip_gemini_status_messages():
    """Gemini CLI status output should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("Gemini CLI v1.2.3")
    assert not should_keep_prompt("Using model: gemini-2.5-pro")
    assert not should_keep_prompt("Tools available: 8")
    assert not should_keep_prompt("MCP servers: 2 connected")
    assert not should_keep_prompt("!ls -la")  # shell escape
    assert not should_keep_prompt("!git status")


def test_skip_cline_tool_blocks():
    """Cline XML tool invocation blocks should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt(
        "<write_to_file>\n<path>src/utils.ts</path>\n<content>code</content>"
    )
    assert not should_keep_prompt("<execute_command>\n<command>npm install</command>")
    assert not should_keep_prompt("<attempt_completion>\n<result>Done.</result>")
    assert not should_keep_prompt("You did not use a tool in your previous response! Please retry.")


def test_skip_language_runtime_commands():
    """Language runtime invocations should be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert not should_keep_prompt("python3 -m pytest tests/ -v")
    assert not should_keep_prompt("node server.js --port 3000")
    assert not should_keep_prompt("go build ./cmd/app")
    assert not should_keep_prompt("pipx install ctxray")


def test_keep_real_prompts_about_tools():
    """Real questions mentioning tool names should NOT be filtered."""
    from ctxray.adapters.filters import should_keep_prompt

    assert should_keep_prompt("how do I configure aider to use a different model?")
    assert should_keep_prompt("explain the gemini cli session format")
    assert should_keep_prompt("what cline tools are available for file editing?")
    assert should_keep_prompt("why is my cursor compositor crashing?")
    assert should_keep_prompt("set up a python virtual environment for this project")


def test_extracts_project_name_from_subagent_session():
    adapter = ClaudeCodeAdapter()
    # Subagent path: .../{project-dir}/{session-uuid}/subagents/agent-*.jsonl
    name = adapter._project_from_path(
        "/Users/chris/.claude/projects/-Users-chris-projects-claudeAutomation"
        "/6279adc7-cb18-477a-8af5-5924579d08aa/subagents/agent-abc123.jsonl"
    )
    assert name == "claudeAutomation [subagent]"


def test_extracts_project_name_from_subagent_top_level():
    adapter = ClaudeCodeAdapter()
    # Subagent in top-level project (no sub-project)
    name = adapter._project_from_path(
        "/Users/chris/.claude/projects/-Users-chris-projects-ctxray"
        "/03d22aee-59fe-4b2a-af1d-ae7d871f816e/subagents/agent-xyz.jsonl"
    )
    assert name == "ctxray [subagent]"


def test_skill_invocations_pass_filter():
    """Skill invocations are NOT filtered — they are categorized as skill_invocation."""
    from ctxray.adapters.filters import should_keep_prompt

    # Skill invocations pass the filter (categorized later in library.py)
    assert should_keep_prompt("请使用 superpowers:executing-plans 执行 docs/plans/foo.md")
    assert should_keep_prompt("use the feature-dev:feature-dev skill")
    assert should_keep_prompt("invoke code-simplifier:simplify on this file")
    # Regular prompts also pass
    assert should_keep_prompt("请使用Python写一个排序函数")
    assert should_keep_prompt("what does the brainstorming workflow do?")
