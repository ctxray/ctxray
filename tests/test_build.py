"""Tests for prompt builder."""

from reprompt.core.build import BuildResult, build_prompt


class TestBuildPrompt:
    """Core build_prompt() tests."""

    def test_task_only(self):
        """Minimal build with just a task."""
        result = build_prompt("fix the auth bug")
        assert isinstance(result, BuildResult)
        assert "Fix the auth bug" in result.prompt
        assert result.score > 0
        assert result.tier in ("DRAFT", "BASIC", "GOOD", "STRONG", "EXPERT")
        assert "task" in result.components_used

    def test_task_with_context(self):
        result = build_prompt("fix the auth bug", context="users get 401 on expired tokens")
        assert "Context:" in result.prompt or "<context>" in result.prompt
        assert "context" in result.components_used

    def test_task_with_files(self):
        result = build_prompt("fix the auth bug", files=["src/auth.ts"])
        assert "src/auth.ts" in result.prompt
        assert "files" in result.components_used

    def test_task_with_multiple_files(self):
        result = build_prompt("refactor", files=["a.py", "b.py"])
        assert "a.py" in result.prompt
        assert "b.py" in result.prompt

    def test_task_with_error(self):
        result = build_prompt(
            "fix the crash", error="TypeError: Cannot read property 'exp' of undefined"
        )
        assert "TypeError" in result.prompt
        assert "error" in result.components_used

    def test_task_with_constraints(self):
        result = build_prompt(
            "refactor the code", constraints=["don't modify tests", "keep backward compat"]
        )
        assert "don't modify tests" in result.prompt
        assert "constraints" in result.components_used

    def test_single_constraint(self):
        result = build_prompt("fix it", constraints=["don't break tests"])
        assert "Constraint:" in result.prompt or "<constraints>" in result.prompt

    def test_task_with_examples(self):
        result = build_prompt("parse dates", examples="Input: 2026-01-01\nOutput: Jan 1, 2026")
        assert "2026-01-01" in result.prompt
        assert "examples" in result.components_used

    def test_task_with_output_format(self):
        result = build_prompt("analyze data", output_format="JSON with fields: name, score")
        assert "JSON" in result.prompt
        assert "output_format" in result.components_used

    def test_task_with_role(self):
        result = build_prompt("review this PR", role="a senior security engineer")
        assert "senior security engineer" in result.prompt
        assert "role" in result.components_used

    def test_full_build(self):
        """Build with all components."""
        result = build_prompt(
            "fix the authentication middleware",
            context="token expiration not handled",
            files=["src/auth/middleware.ts"],
            error="401 on expired tokens",
            constraints=["don't modify tests", "keep backward compat"],
            examples="Expected: refresh token automatically",
            output_format="code with inline comments",
            role="a senior backend engineer",
        )
        assert result.score > 40
        assert len(result.components_used) == 8
        assert len(result.suggestions) == 0  # all components provided


class TestImperativeForm:
    """Tests for _ensure_imperative."""

    def test_strips_please(self):
        result = build_prompt("please fix the bug")
        assert result.prompt.startswith("Fix the bug")

    def test_strips_can_you(self):
        result = build_prompt("can you fix the bug")
        assert result.prompt.startswith("Fix the bug")

    def test_strips_wondering(self):
        result = build_prompt("I was wondering if you could fix the bug")
        assert "wondering" not in result.prompt

    def test_preserves_imperative(self):
        result = build_prompt("Fix the bug")
        assert "Fix the bug" in result.prompt

    def test_capitalizes_first_letter(self):
        result = build_prompt("add a test for the parser")
        assert result.prompt.startswith("Add a test")


class TestModelFormatting:
    """Tests for model-specific formatting."""

    def test_claude_xml_tags(self):
        """Claude model should use XML tags for multi-part prompts."""
        result = build_prompt(
            "fix the bug",
            context="auth fails",
            constraints=["no breaking changes"],
            model="claude",
        )
        assert "<context>" in result.prompt
        assert "<constraints>" in result.prompt

    def test_gpt_markdown_headers(self):
        """GPT model should use markdown headers."""
        result = build_prompt(
            "fix the bug",
            context="auth fails",
            constraints=["no breaking changes"],
            model="gpt",
        )
        assert "## Context" in result.prompt
        assert "## Constraints" in result.prompt

    def test_default_plain_text(self):
        """Default formatting uses plain text."""
        result = build_prompt(
            "fix the bug",
            context="auth fails",
            constraints=["no breaking changes"],
        )
        assert "Context:" in result.prompt
        assert "<context>" not in result.prompt
        assert "##" not in result.prompt

    def test_short_prompt_no_xml(self):
        """Short prompts (<=2 parts) skip XML/markdown even with model set."""
        result = build_prompt("fix the bug", model="claude")
        assert "<" not in result.prompt or result.prompt.count("<") == 0

    def test_short_prompt_no_markdown(self):
        result = build_prompt("fix the bug", model="gpt")
        assert "##" not in result.prompt

    def test_claude_error_in_context_tag(self):
        result = build_prompt(
            "fix crash",
            error="NullPointerException",
            constraints=["keep tests"],
            model="claude",
        )
        assert "<context>" in result.prompt
        assert "NullPointerException" in result.prompt


class TestScoring:
    """Tests for scoring integration."""

    def test_score_increases_with_context(self):
        """Adding context should generally improve score."""
        bare = build_prompt("fix the authentication middleware bug")
        rich = build_prompt(
            "fix the authentication middleware bug",
            files=["src/auth.ts"],
            error="401 on expired tokens",
            constraints=["keep backward compatibility"],
        )
        assert rich.score >= bare.score

    def test_tier_label_assigned(self):
        result = build_prompt("fix the auth bug")
        assert result.tier in ("DRAFT", "BASIC", "GOOD", "STRONG", "EXPERT")

    def test_tier_expert(self):
        """A fully loaded prompt should score high."""
        result = build_prompt(
            "fix the authentication middleware to handle token expiration properly",
            context="users are getting 401 errors when their JWT expires during long sessions",
            files=["src/auth/middleware.ts", "src/auth/token.ts"],
            error="TypeError: Cannot read property 'exp' of undefined at verifyToken line 42",
            constraints=[
                "don't modify existing unit tests",
                "keep backward compatibility with v1 tokens",
                "log all token refresh attempts",
            ],
            examples="Expected: expired token triggers automatic refresh, not 401",
            output_format="TypeScript code with inline comments explaining changes",
            role="a senior backend engineer specializing in authentication",
        )
        assert result.score >= 50  # well-structured prompts should score well


class TestSuggestions:
    """Tests for missing-component suggestions."""

    def test_bare_task_has_suggestions(self):
        result = build_prompt("fix the bug")
        assert len(result.suggestions) > 0

    def test_suggestions_mention_missing(self):
        result = build_prompt("fix the bug")
        suggestion_text = " ".join(result.suggestions)
        assert "--file" in suggestion_text
        assert "--error" in suggestion_text
        assert "--constraint" in suggestion_text

    def test_no_file_suggestion_when_provided(self):
        result = build_prompt("fix bug", files=["src/app.py"])
        suggestion_text = " ".join(result.suggestions)
        assert "--file" not in suggestion_text

    def test_no_error_suggestion_when_provided(self):
        result = build_prompt("fix bug", error="TypeError")
        suggestion_text = " ".join(result.suggestions)
        assert "--error" not in suggestion_text

    def test_all_provided_no_suggestions(self):
        result = build_prompt(
            "fix bug",
            context="c",
            files=["f"],
            error="e",
            constraints=["x"],
            examples="ex",
            role="r",
            output_format="json",
        )
        assert len(result.suggestions) == 0

    def test_suggestions_include_points(self):
        result = build_prompt("fix the bug")
        for s in result.suggestions:
            assert "pts" in s


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_task(self):
        result = build_prompt("")
        assert isinstance(result, BuildResult)

    def test_task_with_period(self):
        """Task already ending with period shouldn't get double period."""
        result = build_prompt("Fix the authentication bug.")
        assert ".." not in result.prompt

    def test_task_with_exclamation(self):
        result = build_prompt("Fix this now!")
        assert "!." not in result.prompt

    def test_unicode_task(self):
        result = build_prompt("修复认证中间件的bug")
        assert "修复" in result.prompt

    def test_long_task(self):
        task = "fix " + "the authentication middleware " * 10
        result = build_prompt(task)
        assert isinstance(result, BuildResult)

    def test_empty_constraints_list(self):
        result = build_prompt("fix bug", constraints=[])
        assert "constraints" not in result.components_used
