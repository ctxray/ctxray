"""Tests for GitHub PR comment markdown generator.

Tests the "Coach, not Judge" design:
- Three display tiers: celebrate (≥70), encourage (50-69), minimal (<50)
- No ❌ for quality scores
- "Items to review" not "violations"
- CI gate uses ⚠️/✅, not ❌
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
        # Scale dimensions proportionally to avg
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


# ── Structure & Branding ──


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


# ── Celebrate Mode (≥70) ──


class TestCelebrateMode:
    def test_shows_score(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "75" in result

    def test_no_decorative_emoji(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "✨" not in result
        assert "🎉" not in result
        assert "🚀" not in result

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
        assert "█" in result
        assert "░" in result

    def test_no_dimension_numbers(self):
        """Bars only — no '21/25' or '8/15' grading numbers."""
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "/25" not in result
        assert "/20" not in result
        assert "/15" not in result

    def test_no_editorial_language(self):
        """No coaching phrases like 'well-structured' — just data."""
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "well-structured" not in result
        assert "push even higher" not in result

    def test_suggestions_neutral_label(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "suggestion" in result

    def test_prompt_count(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        assert "10" in result  # total_prompts


# ── Encourage Mode (50-69) ──


class TestEncourageMode:
    def test_no_total_score(self):
        """Total score number should NOT appear in encourage mode."""
        result = generate_pr_comment(_scored_data(avg_score=60))
        # "60" might appear in dimension values, but not as "60/100"
        assert "/100" not in result

    def test_shows_dimensions(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "Clarity" in result
        assert "Context" in result

    def test_no_tier_label(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "Strong" not in result
        assert "Good" not in result
        assert "Basic" not in result

    def test_shows_suggestions(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "suggestion" in result

    def test_no_decorative_emoji(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "✨" not in result

    def test_shows_points_potential(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "pts potential" in result


# ── Minimal Mode (<50) ──


class TestMinimalMode:
    def test_no_total_score(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "/100" not in result

    def test_no_dimensions(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "Clarity" not in result
        assert "Context" not in result

    def test_no_tier_label(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "Basic" not in result
        assert "Draft" not in result

    def test_shows_suggestions(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "suggestion" in result

    def test_no_decorative_emoji(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "✨" not in result

    def test_prompt_count_shown(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "10" in result


# ── No Score (lint only) ──


class TestNoScore:
    def test_no_dimensions(self):
        result = generate_pr_comment(_base_data())
        assert "Clarity" not in result

    def test_all_clear_when_no_violations(self):
        result = generate_pr_comment(_base_data())
        assert "all clear" in result
        assert "✅" in result

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


# ── No Shaming (core principle) ──


class TestNoShaming:
    """Verify the PR comment never uses shaming language or symbols."""

    def test_no_red_x_at_any_score(self):
        """❌ should NEVER appear for quality scores."""
        for score in [10, 25, 35, 45, 55, 65, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            assert "❌" not in result, f"❌ appeared at score {score}"

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
        """🔴 should not appear — too alarming for quality suggestions."""
        data = _base_data(
            errors=2,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
                {"rule": "vague", "severity": "error", "message": "Vague", "prompt": "fix it"},
            ],
        )
        result = generate_pr_comment(data)
        assert "🔴" not in result

    def test_no_basic_or_draft_labels(self):
        for score in [10, 25, 35, 45]:
            result = generate_pr_comment(_scored_data(avg_score=score))
            assert "Basic" not in result
            assert "BASIC" not in result
            assert "Draft" not in result
            assert "DRAFT" not in result

    def test_no_decorative_emoji_anywhere(self):
        """Decorative emoji (✨🎉🚀🎊) should never appear — reads as AI-generated."""
        for score in [10, 35, 55, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            for emoji in ["✨", "🎉", "🚀", "🎊"]:
                assert emoji not in result, f"{emoji} appeared at score {score}"

    def test_no_editorial_language_anywhere(self):
        """No coaching phrases at any score level."""
        for score in [35, 55, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            for phrase in ["well-structured", "push even higher", "quick wins", "great job"]:
                assert phrase not in result, f"'{phrase}' appeared at score {score}"

    def test_no_dimension_scores_anywhere(self):
        """Dimension bars must never show numbers like '8/15' — only visual bars."""
        for score in [55, 75, 90]:
            result = generate_pr_comment(_scored_data(avg_score=score, threshold=0))
            for suffix in ["/25", "/20", "/15"]:
                assert suffix not in result, f"'{suffix}' appeared at score {score}"


# ── Suggestions ──


class TestSuggestions:
    def test_suggestions_collapsible(self):
        result = generate_pr_comment(_scored_data(avg_score=60))
        assert "<details>" in result
        assert "View suggestions" in result

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
        assert "View suggestions" not in result

    def test_suggestions_present_in_minimal_mode(self):
        result = generate_pr_comment(_scored_data(avg_score=35))
        assert "View suggestions" in result

    def test_singular_suggestion(self):
        """'1 suggestion' not '1 suggestions'."""
        data = _scored_data(avg_score=75, with_suggestions=False)
        data["score"]["top_suggestions"] = [
            {"message": "Add constraints", "points": 5, "paper": "", "count": 1, "impact": "med"},
        ]
        result = generate_pr_comment(data)
        assert "1 suggestion" in result
        # Should not have "1 suggestions" (plural)
        assert "1 suggestions" not in result


# ── Lint Items ──


class TestLintItems:
    def test_items_use_neutral_language(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "item to review" in result  # singular for 1 item

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
        assert "⚠️" in result

    def test_warning_uses_lightbulb(self):
        data = _base_data(
            warnings=1,
            violations=[
                {"rule": "short", "severity": "warning", "message": "Short", "prompt": "hi"},
            ],
        )
        result = generate_pr_comment(data)
        assert "💡" in result

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


# ── CI Gate ──


class TestCIGate:
    def test_gate_pass_shows_checkmark(self):
        data = _scored_data(avg_score=75, threshold=50, passed=True)
        result = generate_pr_comment(data)
        assert "✅" in result
        assert "Meets project target" in result
        assert "75 ≥ 50" in result

    def test_gate_fail_shows_warning(self):
        data = _scored_data(avg_score=40, threshold=50, passed=False)
        result = generate_pr_comment(data)
        assert "⚠️" in result
        assert "Below project target" in result
        assert "40 < 50" in result

    def test_gate_fail_no_red_x(self):
        """Even CI gate failure uses ⚠️, not ❌."""
        data = _scored_data(avg_score=30, threshold=50, passed=False)
        result = generate_pr_comment(data)
        assert "❌" not in result

    def test_no_gate_when_threshold_zero(self):
        data = _scored_data(avg_score=75, threshold=0)
        result = generate_pr_comment(data)
        assert "project target" not in result
        assert "Meets" not in result

    def test_gate_present_in_minimal_mode(self):
        """CI gate message appears even when score is low."""
        data = _scored_data(avg_score=30, threshold=50, passed=False)
        result = generate_pr_comment(data)
        assert "Below project target" in result


# ── Edge Cases ──


class TestEdgeCases:
    def test_zero_prompts(self):
        result = generate_pr_comment(_base_data(total_prompts=0))
        assert "0" in result
        assert COMMENT_MARKER in result

    def test_score_without_dimensions(self):
        data = _scored_data(avg_score=75, with_dims=False)
        result = generate_pr_comment(data)
        assert "75" in result  # score shown in celebrate
        assert "Clarity" not in result  # no dims

    def test_boundary_70_is_celebrate(self):
        result = generate_pr_comment(_scored_data(avg_score=70))
        assert "70" in result  # score shown
        assert "Strong" in result

    def test_boundary_69_is_encourage(self):
        result = generate_pr_comment(_scored_data(avg_score=69))
        assert "✨" not in result
        assert "/100" not in result
        assert "Clarity" in result  # dimensions shown

    def test_boundary_50_is_encourage(self):
        result = generate_pr_comment(_scored_data(avg_score=50))
        assert "Clarity" in result
        assert "/100" not in result

    def test_boundary_49_is_minimal(self):
        result = generate_pr_comment(_scored_data(avg_score=49))
        assert "Clarity" not in result
        assert "/100" not in result

    def test_valid_markdown_dimension_table(self):
        result = generate_pr_comment(_scored_data(avg_score=75))
        lines = result.split("\n")
        header_lines = [line for line in lines if line.startswith("|") and "Clarity" in line]
        assert len(header_lines) == 1
        idx = lines.index(header_lines[0])
        assert ":---:" in lines[idx + 1]
