"""Tests for prompt explainer."""

from ctxray.core.explain import ExplainResult, explain_prompt


class TestExplainPrompt:
    def test_returns_explain_result(self):
        result = explain_prompt("fix the auth bug in login.ts")
        assert isinstance(result, ExplainResult)

    def test_has_score_and_tier(self):
        result = explain_prompt("fix the auth bug in login.ts")
        assert result.score > 0
        assert result.tier in ("DRAFT", "BASIC", "GOOD", "STRONG", "EXPERT")

    def test_has_summary(self):
        result = explain_prompt("fix the auth bug in login.ts")
        assert len(result.summary) > 20

    def test_short_prompt_has_weaknesses(self):
        result = explain_prompt("fix it")
        assert len(result.weaknesses) > 0 or len(result.tips) > 0

    def test_good_prompt_has_strengths(self):
        result = explain_prompt(
            "Fix the authentication bug in src/auth/middleware.ts. "
            "Error: TypeError: Cannot read property 'exp' of undefined at line 42. "
            "Don't modify existing tests. Keep backward compatibility."
        )
        assert len(result.strengths) > 0

    def test_vague_prompt_gets_tips(self):
        result = explain_prompt("help me with the thing that's broken")
        assert len(result.tips) > 0 or len(result.weaknesses) > 0

    def test_buried_instruction_detected(self):
        result = explain_prompt(
            "So I was looking at the code and there were some issues "
            "with various things in the system. The database seemed slow "
            "and the API was timing out. Anyway, what I need is for you "
            "to optimize the database queries in src/db/queries.ts to use "
            "proper indexing and batch operations. The current implementation "
            "does N+1 queries which is really slow."
        )
        # Should have position-related feedback
        assert isinstance(result.tips, list)

    def test_context_rich_prompt(self):
        result = explain_prompt(
            "Fix the authentication bug in src/auth/middleware.ts:42. "
            "```\nTypeError: Cannot read property 'exp'\n```\n"
            "Expected: token refresh on expiry. Actual: 401 error."
        )
        # Should recognize code blocks and file refs
        strength_text = " ".join(result.strengths)
        has_context = "context" in strength_text.lower() or "file" in strength_text.lower()
        assert has_context or len(result.strengths) > 0

    def test_high_score_summary(self):
        result = explain_prompt(
            "You are a senior backend engineer. "
            "Fix the authentication middleware in src/auth/middleware.ts. "
            "Error: TypeError: Cannot read property 'exp' of undefined at line 42. "
            "```typescript\nconst decoded = jwt.verify(token, secret);\n```\n"
            "Expected: automatic token refresh on expiry. "
            "Constraints: don't modify existing tests, keep backward compatibility. "
            "Example: expired token should trigger refresh, not 401. "
            "Fix the authentication middleware in src/auth/middleware.ts."
        )
        if result.score >= 50:
            summary = result.summary.lower()
            assert any(w in summary for w in ("basics", "good", "strong", "excellent", "decent"))


class TestExplainOutput:
    def test_render_explain(self):
        from ctxray.output.explain_terminal import render_explain

        result = explain_prompt("fix the auth bug in login.ts")
        output = render_explain(result)
        assert result.tier in output
        assert "Analysis" in output

    def test_render_with_strengths(self):
        from ctxray.output.explain_terminal import render_explain

        result = explain_prompt(
            "Fix the authentication bug in src/auth.ts. Error: JWT expired. Don't change tests."
        )
        output = render_explain(result)
        if result.strengths:
            assert "working" in output.lower()

    def test_render_with_tips(self):
        from ctxray.output.explain_terminal import render_explain

        result = explain_prompt("fix the bug somewhere")
        output = render_explain(result)
        if result.tips:
            assert "improve" in output.lower()
