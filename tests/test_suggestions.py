"""Unit tests for command journey suggestions."""

from __future__ import annotations

from reprompt.core.suggestions import SUGGESTIONS, get_suggestion


class TestGetSuggestion:
    def test_all_five_commands_have_suggestions(self):
        expected = {"scan", "report", "score", "insights", "distill"}
        assert set(SUGGESTIONS.keys()) == expected

    def test_scan_returns_suggestion(self):
        hint = get_suggestion("scan")
        assert hint is not None
        assert "reprompt report" in hint

    def test_report_returns_suggestion(self):
        hint = get_suggestion("report")
        assert hint is not None
        assert "reprompt insights" in hint

    def test_score_returns_suggestion(self):
        hint = get_suggestion("score")
        assert hint is not None
        assert "reprompt compress" in hint

    def test_insights_returns_suggestion(self):
        hint = get_suggestion("insights")
        assert hint is not None
        assert "reprompt distill" in hint

    def test_distill_returns_suggestion(self):
        hint = get_suggestion("distill")
        assert hint is not None
        assert "reprompt distill --export" in hint

    def test_unknown_command_returns_none(self):
        assert get_suggestion("nonexistent") is None
        assert get_suggestion("") is None

    def test_suggestions_contain_valid_command_names(self):
        valid_commands = {
            "reprompt report",
            "reprompt insights",
            "reprompt distill",
            "reprompt compress",
            "reprompt score",
        }
        for cmd, hint in SUGGESTIONS.items():
            # Each suggestion should reference at least one valid command
            assert any(vc in hint for vc in valid_commands), (
                f"Suggestion for '{cmd}' lacks valid command reference: {hint}"
            )
