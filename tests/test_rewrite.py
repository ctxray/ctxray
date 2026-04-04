"""Tests for prompt rewrite engine."""

from __future__ import annotations

from ctxray.core.rewrite import RewriteResult, rewrite_prompt


class TestRewritePrompt:
    def test_returns_rewrite_result(self):
        result = rewrite_prompt("I was wondering if you could fix the authentication bug")
        assert isinstance(result, RewriteResult)
        assert result.original != ""
        assert result.rewritten != ""
        assert isinstance(result.score_before, float)
        assert isinstance(result.score_after, float)

    def test_removes_hedging(self):
        result = rewrite_prompt(
            "I was wondering if you could perhaps maybe help me fix the login bug"
        )
        assert "I was wondering" not in result.rewritten
        assert "perhaps" not in result.rewritten
        assert "maybe" not in result.rewritten
        assert any("hedging" in c.lower() for c in result.changes)

    def test_removes_filler(self):
        result = rewrite_prompt(
            "Basically, I would really like you to please help me with refactoring "
            "the authentication module. If you don't mind, could you sort of simplify "
            "the code a little bit and make it cleaner?"
        )
        assert len(result.changes) > 0
        assert "basically" not in result.rewritten.lower().split(",")[0]

    def test_score_improves_or_stays(self):
        result = rewrite_prompt(
            "I was wondering if you could please help me to basically just fix the bug "
            "that is kind of causing issues in the system somewhere"
        )
        # Score should not decrease significantly
        assert result.score_after >= result.score_before - 5

    def test_good_prompt_minimal_changes(self):
        result = rewrite_prompt(
            "Fix the JWT token expiration bug in src/auth/middleware.ts line 42. "
            "The token validation returns 401 even with valid tokens. "
            "Error: 'TokenExpiredError: jwt expired'. "
            "Do not modify the refresh token logic."
        )
        # A well-written prompt should have few or no changes
        assert len(result.changes) <= 2

    def test_manual_suggestions_for_vague_prompt(self):
        result = rewrite_prompt("fix the authentication error in the login flow")
        # Should suggest adding code/errors
        assert len(result.manual_suggestions) > 0

    def test_manual_suggestions_include_constraints(self):
        result = rewrite_prompt("refactor the database connection pool to use async operations")
        suggestions_text = " ".join(result.manual_suggestions).lower()
        assert "constraint" in suggestions_text or "format" in suggestions_text

    def test_echo_key_requirement_for_long_prompt(self):
        long_prompt = (
            "Refactor the authentication module to use OAuth2 with PKCE flow. "
            "The current implementation uses session cookies which don't work "
            "well with our mobile app. We need to support both web and mobile "
            "clients. The backend is Express.js with PostgreSQL. "
            "Current auth middleware is in src/middleware/auth.ts. "
            "We also have rate limiting in src/middleware/rate-limit.ts that "
            "needs to work with the new auth flow."
        )
        result = rewrite_prompt(long_prompt)
        # For long prompts with low repetition, should echo
        if any("echo" in c.lower() for c in result.changes):
            assert "Important:" in result.rewritten

    def test_preserves_code_blocks(self):
        result = rewrite_prompt(
            "I was wondering if you could fix this code:\n"
            "```python\n"
            "def login(user):\n"
            "    return None\n"
            "```\n"
            "It should return a token."
        )
        assert "```python" in result.rewritten
        assert "def login" in result.rewritten

    def test_json_serializable(self):
        import json

        result = rewrite_prompt("fix the bug in the login page")
        data = {
            "original": result.original,
            "rewritten": result.rewritten,
            "score_before": result.score_before,
            "score_after": result.score_after,
            "changes": result.changes,
            "manual_suggestions": result.manual_suggestions,
        }
        # Should not raise
        json.dumps(data)

    def test_short_prompt_gets_suggestions(self):
        result = rewrite_prompt("fix the auth bug")
        assert len(result.manual_suggestions) > 0

    def test_no_crash_on_empty_like_input(self):
        result = rewrite_prompt("x")
        assert isinstance(result, RewriteResult)

    # -- Layer 5: Task-specific scaffold tests --

    def test_debug_scaffold_adds_error_slot(self):
        result = rewrite_prompt("fix the auth bug")
        # Short debug prompt should get error/file/code scaffold
        has_scaffold = any("debug" in c.lower() or "structure" in c.lower() for c in result.changes)
        suggestions_text = " ".join(result.manual_suggestions).lower()
        has_error_slot = "Error:" in result.rewritten or "error" in suggestions_text
        assert has_scaffold or has_error_slot

    def test_implement_scaffold_adds_io_spec(self):
        result = rewrite_prompt("implement user login")
        # Should suggest I/O spec or constraints
        all_text = result.rewritten + " ".join(result.manual_suggestions)
        has_io = "Input/Output:" in all_text or "input/output" in all_text.lower()
        has_constraints = "Constraints:" in all_text or "constraint" in all_text.lower()
        assert has_io or has_constraints

    def test_refactor_scaffold_adds_scope(self):
        result = rewrite_prompt("refactor the auth module")
        all_text = result.rewritten + " ".join(result.manual_suggestions)
        has_scope = "Scope:" in all_text or "file" in all_text.lower()
        assert has_scope

    def test_test_scaffold_adds_target(self):
        result = rewrite_prompt("write tests for login")
        all_text = result.rewritten + " ".join(result.manual_suggestions)
        lower_text = all_text.lower()
        has_target = "Target:" in all_text or "function" in lower_text or "edge" in lower_text
        assert has_target

    def test_long_prompt_no_scaffold(self):
        # Long prompts (>30 words) should NOT get scaffold
        long_prompt = (
            "Fix the authentication bug in src/auth/middleware.ts where the JWT token "
            "expiration check fails for tokens issued before the timezone migration. "
            "The error is TypeError: Cannot read property 'exp' of undefined at line 42. "
            "Do not modify the refresh token logic."
        )
        result = rewrite_prompt(long_prompt)
        has_scaffold = any("structure" in c.lower() for c in result.changes)
        assert not has_scaffold

    def test_scaffold_not_duplicated(self):
        # If prompt already has error message, don't add Error: slot
        result = rewrite_prompt("fix the TypeError in auth.ts")
        # Should not scaffold Error: because error message is present
        assert result.rewritten.count("Error:") <= 1


class TestRewriteCLI:
    def test_rewrite_command_exists(self):
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["rewrite", "--help"])
        assert result.exit_code == 0
        assert "rewrite" in result.output.lower()

    def test_rewrite_json_output(self):
        import json

        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app, ["rewrite", "fix the authentication error in login flow", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "original" in data
        assert "rewritten" in data
        assert "score_before" in data
        assert "score_after" in data
        assert "changes" in data

    def test_rewrite_terminal_output(self):
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "rewrite",
                "I was wondering if you could please help me fix the authentication bug",
            ],
        )
        assert result.exit_code == 0
