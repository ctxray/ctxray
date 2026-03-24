"""Tests for distill CLI command and terminal output."""

from __future__ import annotations

import json
import re
import tempfile

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text (Rich color output on CI)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestRenderDistill:
    def test_render_basic(self):
        from reprompt.output.distill_terminal import render_distill

        turns = [
            ConversationTurn(
                role="user",
                text="Fix the bug",
                timestamp="2026-03-23T10:00:00Z",
                turn_index=0,
                importance=0.85,
            ),
            ConversationTurn(
                role="assistant",
                text="I'll fix the bug by editing auth.py...",
                timestamp="2026-03-23T10:00:05Z",
                turn_index=1,
                importance=0.7,
            ),
        ]
        conv = Conversation(
            session_id="abc123",
            source="claude-code",
            project="reprompt",
            turns=turns,
            duration_seconds=2700,
        )
        result = DistillResult(
            conversation=conv,
            filtered_turns=turns,
            threshold=0.3,
            stats=DistillStats(
                total_turns=47,
                kept_turns=2,
                retention_ratio=0.04,
                total_duration_seconds=2700,
            ),
        )
        output = render_distill(result)
        assert "abc123" in output
        assert "claude-code" in output
        assert "Fix the bug" in output

    def test_render_stars(self):
        from reprompt.output.distill_terminal import render_distill

        turns = [
            ConversationTurn(
                role="user", text="High importance turn", timestamp="", turn_index=0, importance=0.9
            ),
            ConversationTurn(
                role="user",
                text="Medium importance turn",
                timestamp="",
                turn_index=2,
                importance=0.5,
            ),
            ConversationTurn(
                role="user", text="Low importance turn", timestamp="", turn_index=4, importance=0.3
            ),
        ]
        conv = Conversation(session_id="t", source="test", project=None, turns=turns)
        result = DistillResult(
            conversation=conv,
            filtered_turns=turns,
            threshold=0.3,
            stats=DistillStats(total_turns=6, kept_turns=3),
        )
        output = render_distill(result)
        assert output  # Just verify no crash

    def test_render_empty(self):
        from reprompt.output.distill_terminal import render_distill

        conv = Conversation(session_id="t", source="test", project=None, turns=[])
        result = DistillResult(
            conversation=conv,
            filtered_turns=[],
            threshold=0.3,
            stats=DistillStats(),
        )
        output = render_distill(result)
        assert "0" in output or "No key turns" in output

    def test_render_summary_mode(self):
        from reprompt.output.distill_terminal import render_distill_summary

        result = DistillResult(
            conversation=Conversation(session_id="t", source="test", project="proj", turns=[]),
            filtered_turns=[],
            threshold=0.3,
            summary="Session (proj): Fix the auth system\n\nKey decisions:\n  - Use JWT",
            files_changed=["src/auth.py"],
            stats=DistillStats(total_turns=10, kept_turns=3),
        )
        output = render_distill_summary(result)
        assert "Fix the auth" in output or "JWT" in output


runner = CliRunner()


class TestDistillCLI:
    def test_distill_no_sessions(self):
        """When no sessions exist, should show helpful message."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["distill"], env={"REPROMPT_DB_PATH": f.name})
        assert result.exit_code == 0
        assert "No sessions found" in result.output or "scan" in result.output.lower()

    def test_distill_json_flag(self):
        """--json flag should produce valid JSON even if empty."""
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            result = runner.invoke(app, ["distill", "--json"], env={"REPROMPT_DB_PATH": f.name})
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, (dict, list))

    def test_distill_help(self):
        result = runner.invoke(app, ["distill", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "--last" in output
        assert "--summary" in output
        assert "--threshold" in output
        assert "--copy" in output
        assert "--json" in output
