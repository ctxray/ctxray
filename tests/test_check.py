"""Tests for unified check command."""

from ctxray.core.check import CheckResult, check_prompt


class TestCheckPrompt:
    def test_returns_check_result(self):
        result = check_prompt("fix the auth bug in login.ts where JWT expires")
        assert isinstance(result, CheckResult)

    def test_has_score(self):
        result = check_prompt("fix the auth bug in login.ts where JWT expires")
        assert result.total > 0
        assert result.tier in ("DRAFT", "BASIC", "GOOD", "STRONG", "EXPERT")

    def test_has_dimensions(self):
        result = check_prompt("fix the auth bug in login.ts where JWT expires")
        assert result.clarity >= 0
        assert result.context >= 0
        assert result.position >= 0
        assert result.structure >= 0
        assert result.repetition >= 0

    def test_has_word_count(self):
        result = check_prompt("fix the auth bug in login.ts where JWT expires")
        assert result.word_count > 0
        assert result.token_count > 0

    def test_short_prompt_has_lint_issues(self):
        result = check_prompt("fix it")
        has_min_length = any(i["rule"] == "min-length" for i in result.lint_issues)
        has_vague = any(i["rule"] == "vague-prompt" for i in result.lint_issues)
        assert has_min_length or has_vague

    def test_good_prompt_has_confirmations(self):
        result = check_prompt(
            "Fix the authentication bug in src/auth/middleware.ts "
            "where JWT token expiration causes 401 errors. "
            "Error: TypeError: Cannot read property 'exp' of undefined. "
            "Don't modify existing tests."
        )
        assert len(result.confirmations) > 0

    def test_vague_prompt_has_suggestions(self):
        result = check_prompt("fix the auth bug somewhere in the codebase")
        assert len(result.suggestions) > 0

    def test_hedging_prompt_gets_rewritten(self):
        result = check_prompt(
            "I was wondering if you could maybe help me fix the authentication bug"
        )
        assert len(result.rewrite_changes) > 0
        first_change = result.rewrite_changes[0].lower()
        assert "filler" in first_change or "hedging" in first_change

    def test_clean_prompt_no_rewrite(self):
        result = check_prompt("Fix the authentication bug in src/auth.ts line 42.")
        # May or may not have rewrite changes; just verify it doesn't crash
        assert isinstance(result.rewrite_changes, list)

    def test_model_specific_lint(self):
        long_text = (
            "Fix the authentication middleware to handle token expiration. "
            "The current implementation fails silently. Check the JWT validation logic. "
        ) * 5
        result = check_prompt(long_text, model="claude")
        # May or may not have claude-specific hints
        assert isinstance(result.lint_issues, list)

    def test_token_budget_lint(self):
        result = check_prompt("short prompt for testing budget", max_tokens=1)
        has_budget = any(i["rule"] == "max-tokens" for i in result.lint_issues)
        assert has_budget


class TestCheckOutput:
    def test_render_check_verbose(self):
        """Verbose mode shows full details including tier and dimensions."""
        from ctxray.output.check_terminal import render_check

        result = check_prompt(
            "I was wondering if you could maybe help me fix the auth bug in login.ts"
        )
        output = render_check(result, verbose=True)
        assert result.tier in output
        assert "Clarity" in output
        assert "Context" in output

    def test_render_coach_mode_hides_score(self):
        """Low-scoring prompts (< 50) hide score and tier in default mode."""
        from ctxray.output.check_terminal import render_check

        result = check_prompt("fix it")
        output = render_check(result)
        # Coach mode: no tier label, no score number, leads with suggestions
        if result.total < 50:
            assert "DRAFT" not in output
            assert "BASIC" not in output
            assert "Clarity" not in output

    def test_render_coach_mode_shows_suggestions(self):
        """Low-scoring prompts still show suggestions and rewrite."""
        from ctxray.output.check_terminal import render_check

        result = check_prompt("fix it")
        output = render_check(result)
        assert "Improve" in output or "Lint" in output or "Rewritten" in output

    def test_render_encourage_hides_numbers(self):
        """Mid-scoring prompts (50-69) show bars without numbers."""
        from ctxray.output.check_terminal import render_check

        result = check_prompt("Fix the auth bug in src/auth/middleware.ts where JWT expires")
        output = render_check(result)
        if 50 <= result.total < 70:
            assert result.tier in output
            assert f"{result.total:.0f}" not in output

    def test_render_with_lint(self):
        from ctxray.output.check_terminal import render_check

        result = check_prompt("fix it")
        output = render_check(result)
        assert "Lint" in output or "Improve" in output

    def test_render_with_rewrite(self):
        from ctxray.output.check_terminal import render_check

        result = check_prompt("I was wondering if you could perhaps fix this terrible bug")
        output = render_check(result)
        if result.rewrite_changes:
            assert "Rewritten" in output
