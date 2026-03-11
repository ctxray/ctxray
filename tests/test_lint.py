"""Tests for prompt linting rules."""

from __future__ import annotations

from reprompt.core.lint import format_lint_results, lint_prompt, lint_prompts


class TestLintPrompt:
    def test_good_prompt_no_violations(self):
        violations = lint_prompt("fix the authentication bug in auth.py — login returns 401")
        assert violations == []

    def test_too_short_error(self):
        violations = lint_prompt("fix bug")
        assert len(violations) == 1
        assert violations[0].rule == "min-length"
        assert violations[0].severity == "error"

    def test_short_warning(self):
        violations = lint_prompt("fix the auth bug please")
        rules = [v.rule for v in violations]
        assert "short-prompt" in rules

    def test_vague_prompt_error(self):
        violations = lint_prompt("fix it")
        rules = [v.rule for v in violations]
        assert "vague-prompt" in rules

    def test_debug_without_reference(self):
        violations = lint_prompt("fix the authentication error in the login flow")
        rules = [v.rule for v in violations]
        assert "debug-needs-reference" in rules

    def test_debug_with_reference_ok(self):
        violations = lint_prompt("fix the authentication error in auth.py login flow")
        rules = [v.rule for v in violations]
        assert "debug-needs-reference" not in rules

    def test_non_debug_no_reference_warning(self):
        """Non-debug prompts don't need file references."""
        violations = lint_prompt("add pagination to the search results page")
        rules = [v.rule for v in violations]
        assert "debug-needs-reference" not in rules


class TestLintPrompts:
    def test_multiple_prompts(self):
        violations = lint_prompts([
            "fix the authentication bug in auth.py — login returns 401",
            "fix it",
            "add pagination to search results with cursor-based navigation",
        ])
        assert len(violations) >= 1  # "fix it" triggers violations

    def test_empty_list(self):
        assert lint_prompts([]) == []


class TestFormatResults:
    def test_no_violations(self):
        result = format_lint_results([], 10)
        assert "no issues found" in result
        assert "10" in result

    def test_with_violations(self):
        violations = lint_prompt("fix it")
        result = format_lint_results(violations, 5)
        assert "error" in result
        assert "fix it" in result

    def test_truncates_long_prompts(self):
        long_prompt = "x" * 100
        violations = lint_prompt(long_prompt)
        # Force a violation for formatting test
        from reprompt.core.lint import LintViolation

        v = LintViolation(
            rule="test", severity="error", message="test", prompt_text=long_prompt
        )
        result = format_lint_results([v], 1)
        assert "..." in result
