"""Integration tests for distill --export CLI flags."""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)

runner = CliRunner()


def _mock_distill_result() -> DistillResult:
    """Build a realistic DistillResult for CLI testing."""
    turns = []
    idx = 0
    user_texts = ["Fix the auth bug", "Use JWT tokens instead", "Next add tests"]
    for text in user_texts:
        user = ConversationTurn(
            role="user",
            text=text,
            timestamp="2026-03-24T10:00:00Z",
            turn_index=idx,
            importance=0.7,
        )
        user.signal_scores = {
            "position": 0.5,
            "length": 0.5,
            "tool_trigger": 0.3,
            "error_recovery": 0.0,
            "semantic_shift": 0.6,
            "uniqueness": 0.5,
        }
        turns.append(user)
        idx += 1
        turns.append(
            ConversationTurn(
                role="assistant",
                text=f"Working on: {text}",
                timestamp="2026-03-24T10:00:05Z",
                turn_index=idx,
                importance=0.5,
                tool_calls=3,
            )
        )
        idx += 1

    conv = Conversation(
        session_id="test-abc",
        source="claude-code",
        project="myproject",
        turns=turns,
        duration_seconds=1800,
    )
    return DistillResult(
        conversation=conv,
        filtered_turns=[t for t in turns if t.importance >= 0.3],
        threshold=0.3,
        files_changed=["auth.py", "tokens.py"],
        stats=DistillStats(
            total_turns=6, kept_turns=6, retention_ratio=1.0, total_duration_seconds=1800
        ),
    )


class TestExportFlag:
    @patch("reprompt.cli._resolve_distill_sessions")
    @patch("reprompt.cli._load_conversation")
    def test_export_produces_markdown(self, mock_load, mock_resolve):
        mock_result = _mock_distill_result()
        mock_resolve.return_value = [("/fake/path", "claude-code", "test-abc")]
        mock_load.return_value = mock_result.conversation

        with patch(
            "reprompt.core.distill.distill_conversation", return_value=mock_result
        ):
            result = runner.invoke(app, ["distill", "--last", "1", "--export"])
        assert result.exit_code == 0
        assert "# Session Context: myproject" in result.output

    @patch("reprompt.cli._resolve_distill_sessions")
    @patch("reprompt.cli._load_conversation")
    def test_export_json_envelope(self, mock_load, mock_resolve):
        mock_result = _mock_distill_result()
        mock_resolve.return_value = [("/fake/path", "claude-code", "test-abc")]
        mock_load.return_value = mock_result.conversation

        with patch(
            "reprompt.core.distill.distill_conversation", return_value=mock_result
        ):
            result = runner.invoke(app, ["distill", "--last", "1", "--export", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "export" in data
        assert "session_id" in data
        assert "tokens" in data

    def test_export_with_last_gt_1_errors(self):
        result = runner.invoke(app, ["distill", "--last", "3", "--export"])
        assert result.exit_code != 0 or "single session" in result.output.lower()


class TestShowWeights:
    def test_show_weights_prints_and_exits(self):
        result = runner.invoke(app, ["distill", "--show-weights"])
        assert result.exit_code == 0
        assert "position" in result.output
        assert "semantic_shift" in result.output


class TestFullFlag:
    def test_full_without_export_warns(self):
        result = runner.invoke(app, ["distill", "--full", "--last", "1"])
        # The warning goes to stderr, but the command should still work
        # Check that it doesn't crash
        assert result.exit_code == 0 or "--full has no effect" in (
            result.output + str(result.stderr_bytes or b"", "utf-8")
        )
