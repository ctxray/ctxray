"""Tests for GitHub PR comment markdown generator.

Tests the redesigned "Coach, not Judge" PR comment:
- GitHub Alerts for instant visual status ([!TIP], [!NOTE], [!WARNING])
- Vertical dimension table with scores (reviewers need numbers for decisions)
- All tiers show numeric score (coach tone, not info hiding)
- Three display tiers: celebrate (>=70), encourage (50-69), minimal (<50)
- No shaming: no decorative emoji, no editorial language
"""

from ctxray.output.github_pr import COMMENT_MARKER, generate_pr_comment


def _base_data(**overrides):
    """Minimal lint data with no score."""
    data = {
        "total_prompts": 10,
        "errors": 0,
        "warnings": 0,
        "violations": [],
    }
    data.update(overrides)
    return data


def _make_score(avg_score=72.5, threshold=50, passed=True, with_dims=True, with_suggestions=True):
    """Build a score dict with configurable avg."""
    score = {
        "avg_score": avg_score,
        "min_score": max(0, avg_score - 30),
        "max_score": min(100, avg_score + 20),
        "threshold": threshold,
        "pass": passed,
    }
    if with_dims:
        ratio = avg_score / 100
        score["dimensions"] = {
            "clarity": {"avg": round(25 * ratio, 1), "max": 25},
            "context": {"avg": round(25 * ratio * 0.8, 1), "max": 25},
            "position": {"avg": round(20 * ratio * 1.1, 1), "max": 20},
            "structure": {"avg": round(15 * ratio * 0.7, 1), "max": 15},
            "repetition": {"avg": round(15 * ratio * 0.6, 1), "max": 15},
        }
    if with_suggestions:
        score["top_suggestions"] = [
            {
                "message": "Add file path references",
                "points": 6,
                "paper": "DETAIL arXiv:2512.02246",
                "impact": "high",
                "count": 4,
            },
            {
                "message": "Move key instruction to start",
                "points": 10,
                "paper": "Lost in the Middle arXiv:2307.03172",
                "impact": "high",
                "count": 3,
            },
        ]
    return score


def _scored_data(avg_score=72.5, **overrides):
    """Lint data with scoring at given avg."""
    threshold = overrides.pop("threshold", 50)
    passed = overrides.pop("passed", avg_score >= threshold)
    data = _base_data(
        score=_make_score(avg_score=avg_score, threshold=threshold, passed=passed, **overrides),
    )
    return data


# -- Structure & Branding --


class TestCommentStructure:
    def test_marker_present(self):
        result = generate_pr_comment(_base_data())
        assert COMMENT_MARKER in result

    def test_marker_is_first_line(self):
        result = generate_pr_comment(_base_data())
        assert result.startswith(COMMENT_MARKER)

    def test_header_is_neutral(self):
        """Header says 'Prompt Quality Report', not a score."""
        result = generate_pr_comment(_scored_data(avg_score=30))
        assert "Prompt Quality Report" in result

    def test_header_neutral_at_all_scores(self):
        for score in [20, 45, 60, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score))
            first_content = result.split("\n")[1]
            assert "Prompt Quality Report" in first_content

    def test_output_ends_with_newline(self):
        result = generate_pr_comment(_base_data())
        assert result.endswith("\n")


class TestBrandedFooter:
    def test_footer_contains_ctxray(self):
        result = generate_pr_comment(_base_data())
        assert "ctxray" in result
        assert "pip install ctxray" in result

    def test_footer_contains_link(self):
        result = generate_pr_comment(_base_data())
        assert "github.com/ctxray/ctxray" in result

    def test_footer_present_at_all_score_levels(self):
        for score in [20, 55, 80]:
            result = generate_pr_comment(_scored_data(avg_score=score))
            assert "pip install ctxray" in result

    def test_footer_has_differentiators(self):
        """Footer shows rule-based, <50ms, no LLM differentiators."""
        result = generate_pr_comment(_base_data())
        assert "rule-based" in result
        assert "<50ms" in result
        assert "no LLM" in result

    def test_footer_says_prompt_quality_linter(self):
        result = generate_pr_comment(_base_data())
        assert "prompt quality linter" in result


# -- GitHub Alerts --


class TestGitHubAlerts:
    def test_celebrate_uses_tip(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "[!TIP]" in result

    def test_encourage_pass_uses_note(self):
        result = generate_pr_comment(_scored_data(avg_score=60, threshold=50, passed=True))
        assert "[!NOTE]" in result

    def test_below_threshold_uses_warning(self):
        result = generate_pr_comment(_scored_data(avg_score=35, threshold=50, passed=False))
        assert "[!WARNING]" in result

    def test_no_threshold_uses_note(self):
        result = generate_pr_comment(_scored_data(avg_score=35, threshold=0))
        assert "[!NOTE]" in result

    def test_alert_present_at_all_scores(self):
        for score in [20, 45, 60, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score))
            assert any(f"[!{t}]" in result for t in ("TIP", "NOTE", "WARNING"))

    def test_alert_contains_score(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "**75**/100" in result

    def test_alert_contains_prompt_count(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "10 prompts" in result


# -- Model Badge --


class TestModelBadge:
    def test_model_in_header(self):
        data = _scored_data(avg_score=75)
        data["model"] = "claude"
        result = generate_pr_comment(data)
        assert "`claude`" in result

    def test_no_model_no_badge(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        # Should not have backtick-wrapped model name
        assert "`claude`" not in result
        assert "`gpt`" not in result

    def test_model_badge_all_types(self):
        for model in ["claude", "gpt", "gemini", "small"]:
            data = _scored_data(avg_score=75)
            data["model"] = model
            result = generate_pr_comment(data)
            assert f"`{model}`" in result


# -- Celebrate Mode (>=70) --


class TestCelebrateMode:
    def test_shows_score(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "**75**/100" in result

    def test_no_decorative_emoji(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "\u2728" not in result
        assert "\U0001f389" not in result
        assert "\U0001f680" not in result

    def test_shows_strong_tier(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "Strong" in result

    def test_shows_expert_tier(self):
        result = generate_pr_comment(_scored_data(avg_score=90))
        assert "Expert" in result

    def test_shows_dimensions(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "Clarity" in result
        assert "Context" in result
        assert "Position" in result
        assert "Structure" in result
        assert "Repetition" in result

    def test_shows_dimension_bars(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "\u2588" in result
        assert "\u2591" in result

    def test_shows_dimension_scores(self):
        """Vertical table shows numeric scores for PR reviewer decisions."""
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "/25" in result
        assert "/20" in result
        assert "/15" in result

    def test_no_editorial_language(self):
        """No coaching phrases like 'well-structured' -- just data."""
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "well-structured" not in result
        assert "push even higher" not in result

    def test_suggestions_neutral_label(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "suggestion" in result

    def test_prompt_count(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "10" in result


# -- Encourage Mode (50-69) --


class TestEncourageMode:
    def test_shows_score_in_alert(self):
        """All tiers show numeric score in PR context."""
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "**60**/100" in result

    def test_shows_dimensions(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "Clarity" in result
        assert "Context" in result

    def test_shows_dimension_scores(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "/25" in result

    def test_no_tier_label(self):
        """No Strong/Expert tier label for encourage range."""
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "Strong" not in result
        assert "Expert" not in result

    def test_shows_suggestions(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "suggestion" in result

    def test_no_decorative_emoji(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "\u2728" not in result

    def test_shows_points_potential(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "pts potential" in result


# -- Minimal Mode (<50) --


class TestMinimalMode:
    def test_shows_score_in_alert(self):
        """All tiers show numeric score in PR context."""
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "**35**/100" in result

    def test_no_dimensions(self):
        """Low scores skip dimensions (all low, not informative)."""
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "Clarity" not in result
        assert "Context" not in result

    def test_no_tier_label(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "Basic" not in result
        assert "Draft" not in result
        assert "Strong" not in result

    def test_shows_suggestions(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "suggestion" in result

    def test_no_decorative_emoji(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "\u2728" not in result

    def test_prompt_count_shown(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "10" in result


# -- No Score (lint only) --


class TestNoScore:
    def test_no_dimensions(self):
        result = generate_pr_comment(_base_data())
        assert "Clarity" not in result

    def test_all_clear_when_no_violations(self):
        result = generate_pr_comment(_base_data())
        assert "all clear" in result
        assert "\u2705" in result

    def test_no_all_clear_when_violations(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "all clear" not in result

    def test_prompt_count(self):
        result = generate_pr_comment(_base_data(total_prompts=42))
        assert "42" in result

    def test_no_github_alert(self):
        """Lint-only mode has no GitHub Alert (no score to show)."""
        result = generate_pr_comment(_base_data())
        assert "[!TIP]" not in result
        assert "[!NOTE]" not in result
        assert "[!WARNING]" not in result


# -- No Shaming (core principle) --


class TestNoShaming:
    """Verify the PR comment never uses shaming language or symbols."""

    def test_no_red_x_at_any_score(self):
        """Cross mark should NEVER appear for quality scores."""
        for score in [10, 25, 35, 45, 55, 65, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            assert "\u274c" not in result, f"cross mark appeared at score {score}"

    def test_no_failed_label(self):
        for score in [10, 35, 45]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            assert "Failed" not in result
            assert "failed" not in result

    def test_no_violation_word(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "violation" not in result.lower()

    def test_no_red_circle_emoji(self):
        data = _base_data(
            errors=2,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
                {"rule": "vague", "severity": "error", "message": "Vague", "prompt": "fix it"},
            ],
        )
        result = generate_pr_comment(data)
        assert "\U0001f534" not in result

    def test_no_basic_or_draft_labels(self):
        for score in [10, 25, 35, 45]:
            result = generate_pr_comment(_scored_data(avg_score=score))
            assert "Basic" not in result
            assert "BASIC" not in result
            assert "Draft" not in result
            assert "DRAFT" not in result

    def test_no_decorative_emoji_anywhere(self):
        for score in [10, 35, 55, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            for emoji in ["\u2728", "\U0001f389", "\U0001f680", "\U0001f38a"]:
                assert emoji not in result, f"decorative emoji appeared at score {score}"

    def test_no_editorial_language_anywhere(self):
        for score in [35, 55, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            for phrase in ["well-structured", "push even higher", "quick wins", "great job"]:
                assert phrase not in result, f"'{phrase}' appeared at score {score}"


# -- Suggestions --


class TestSuggestions:
    def test_suggestions_collapsible(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "<details>" in result
        assert "suggestion" in result

    def test_suggestion_content(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "Add file path references" in result

    def test_suggestion_points(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "+6 pts" in result
        assert "+10 pts" in result

    def test_suggestion_paper_citation(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "arXiv" in result

    def test_suggestion_prompt_count(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "4 prompts" in result

    def test_no_suggestions_section_when_empty(self):
        data = _scored_data(avg_score=75, with_suggestions=False)
        result = generate_pr_comment(data)
        assert "suggestion" not in result

    def test_suggestions_present_in_minimal_mode(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "suggestion" in result

    def test_singular_suggestion(self):
        """'1 suggestion' not '1 suggestions'."""
        data = _scored_data(avg_score=75, with_suggestions=False)
        data["score"]["top_suggestions"] = [
            {"message": "Add constraints", "points": 5, "paper": "", "count": 1, "impact": "med"},
        ]
        result = generate_pr_comment(data)
        assert "1 suggestion" in result
        assert "1 suggestions" not in result


# -- Lint Items --


class TestLintItems:
    def test_items_use_neutral_language(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "item to review" in result

    def test_items_collapsible(self):
        data = _base_data(
            warnings=1,
            violations=[
                {"rule": "short", "severity": "warning", "message": "Short", "prompt": "hi"},
            ],
        )
        result = generate_pr_comment(data)
        assert "<details>" in result

    def test_error_uses_warning_emoji(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "\u26a0\ufe0f" in result

    def test_warning_uses_lightbulb(self):
        data = _base_data(
            warnings=1,
            violations=[
                {"rule": "short", "severity": "warning", "message": "Short", "prompt": "hi"},
            ],
        )
        result = generate_pr_comment(data)
        assert "\U0001f4a1" in result

    def test_items_capped_at_20(self):
        violations = [
            {"rule": f"rule-{i}", "severity": "warning", "message": f"msg {i}", "prompt": "x"}
            for i in range(25)
        ]
        result = generate_pr_comment(_base_data(warnings=25, violations=violations))
        assert "and 5 more" in result

    def test_no_items_section_when_clean(self):
        result = generate_pr_comment(_base_data())
        assert "items to review" not in result


# -- CI Gate (integrated into Alert) --


class TestCIGate:
    def test_gate_pass_shows_checkmark(self):
        data = _scored_data(avg_score=75, threshold=50, passed=True)
        result = generate_pr_comment(data)
        assert "\u2705" in result
        assert "Pass" in result

    def test_gate_fail_shows_warning(self):
        data = _scored_data(avg_score=40, threshold=50, passed=False)
        result = generate_pr_comment(data)
        assert "\u26a0\ufe0f" in result
        assert "Below target" in result

    def test_gate_fail_no_red_x(self):
        data = _scored_data(avg_score=30, threshold=50, passed=False)
        result = generate_pr_comment(data)
        assert "\u274c" not in result

    def test_no_gate_when_threshold_zero(self):
        data = _scored_data(avg_score=75, threshold=0)
        result = generate_pr_comment(data)
        assert "Pass" not in result
        assert "Below" not in result

    def test_gate_present_in_minimal_mode(self):
        data = _scored_data(avg_score=30, threshold=50, passed=False)
        result = generate_pr_comment(data)
        assert "Below target" in result


# -- Edge Cases --


class TestEdgeCases:
    def test_zero_prompts(self):
        result = generate_pr_comment(_base_data(total_prompts=0))
        assert "0" in result
        assert COMMENT_MARKER in result

    def test_score_without_dimensions(self):
        data = _scored_data(avg_score=75, with_dims=False)
        result = generate_pr_comment(data)
        assert "75" in result
        assert "Clarity" not in result

    def test_boundary_70_is_celebrate(self):
        result = generate_pr_comment(_scored_data(avg_score=70))
        assert "**70**/100" in result
        assert "Strong" in result
        assert "[!TIP]" in result

    def test_boundary_69_is_encourage(self):
        result = generate_pr_comment(_scored_data(avg_score=69))
        assert "**69**/100" in result
        assert "Strong" not in result
        assert "Clarity" in result  # dimensions shown
        assert "[!NOTE]" in result

    def test_boundary_50_is_encourage(self):
        result = generate_pr_comment(_scored_data(avg_score=50))
        assert "Clarity" in result
        assert "[!NOTE]" in result

    def test_boundary_49_is_minimal(self):
        result = generate_pr_comment(_scored_data(avg_score=49))
        assert "Clarity" not in result

    def test_valid_markdown_dimension_table(self):
        """Vertical dimension table has correct structure."""
        result = generate_pr_comment(_scored_data(avg_score=75))
        lines = result.split("\n")
        # Find the header row
        header_lines = [line for line in lines if line.strip() == "| Dimension | | |"]
        assert len(header_lines) == 1
        idx = lines.index(header_lines[0])
        assert lines[idx + 1].strip() == "|:--|:--|--:|"
        # Each dimension is a row
        dim_rows = lines[idx + 2 : idx + 7]
        assert any("Clarity" in row for row in dim_rows)
        assert any("Repetition" in row for row in dim_rows)

    def test_vertical_table_has_all_dimensions(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        for dim in ["Clarity", "Context", "Position", "Structure", "Repetition"]:
            assert dim in result
