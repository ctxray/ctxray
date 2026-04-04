"""Unit tests for command journey suggestions."""

from __future__ import annotations

from ctxray.core.suggestions import SUGGESTIONS, get_suggestion


class TestGetSuggestion:
    def test_all_commands_have_suggestions(self):
        expected = {
            "scan",
            "report",
            "score",
            "insights",
            "distill",
            "agent",
            "sessions",
            "repetition",
            "template",
            "lint",
            "rewrite",
            "projects",
            "build",
            "check",
            "explain",
            "patterns",
        }
        assert set(SUGGESTIONS.keys()) == expected

    def test_scan_returns_suggestion(self):
        hint = get_suggestion("scan")
        assert hint is not None
        assert "ctxray report" in hint

    def test_report_returns_suggestion(self):
        hint = get_suggestion("report")
        assert hint is not None
        assert "ctxray insights" in hint

    def test_score_returns_suggestion(self):
        hint = get_suggestion("score")
        assert hint is not None
        assert "ctxray compress" in hint

    def test_insights_returns_suggestion(self):
        hint = get_suggestion("insights")
        assert hint is not None
        assert "ctxray template save" in hint

    def test_distill_returns_suggestion(self):
        hint = get_suggestion("distill")
        assert hint is not None
        assert "ctxray agent" in hint

    def test_agent_returns_suggestion(self):
        hint = get_suggestion("agent")
        assert hint is not None
        assert "ctxray agent --loops-only" in hint

    def test_unknown_command_returns_none(self):
        assert get_suggestion("nonexistent") is None
        assert get_suggestion("") is None

    def test_suggestions_contain_valid_command_names(self):
        valid_commands = {
            "ctxray report",
            "ctxray insights",
            "ctxray distill",
            "ctxray compress",
            "ctxray score",
            "ctxray template",
            "ctxray agent",
            "ctxray sessions",
            "ctxray privacy",
            "ctxray init",
            "ctxray rewrite",
        }
        for cmd, hint in SUGGESTIONS.items():
            # Each suggestion should reference at least one valid command
            assert any(vc in hint for vc in valid_commands), (
                f"Suggestion for '{cmd}' lacks valid command reference: {hint}"
            )
