"""Tests for GitHub PR comment markdown generator."""

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


def _scored_data(**overrides):
    """Lint data with full scoring breakdown."""
    data = _base_data(
        score={
            "avg_score": 72.5,
            "min_score": 35.0,
            "max_score": 95.0,
            "threshold": 50,
            "pass": True,
            "dimensions": {
                "clarity": {"avg": 20.3, "max": 25},
                "context": {"avg": 17.8, "max": 25},
                "position": {"avg": 15.6, "max": 20},
                "structure": {"avg": 10.2, "max": 15},
                "repetition": {"avg": 8.6, "max": 15},
            },
            "tiers": {
                "Expert": 2,
                "Strong": 5,
                "Good": 2,
                "Basic": 1,
                "Draft": 0,
            },
            "top_suggestions": [
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
            ],
        },
    )
    data.update(overrides)
    return data


class TestCommentMarker:
    def test_marker_present(self):
        result = generate_pr_comment(_base_data())
        assert COMMENT_MARKER in result

    def test_marker_is_first_line(self):
        result = generate_pr_comment(_base_data())
        assert result.startswith(COMMENT_MARKER)


class TestBrandedFooter:
    def test_footer_contains_ctxray(self):
        result = generate_pr_comment(_base_data())
        assert "ctxray" in result
        assert "pip install ctxray" in result

    def test_footer_contains_link(self):
        result = generate_pr_comment(_base_data())
        assert "github.com/ctxray/ctxray" in result


class TestNoScore:
    """When scoring is not enabled (basic lint only)."""

    def test_header_shows_lint(self):
        result = generate_pr_comment(_base_data())
        assert "ctxray lint" in result

    def test_passed_no_issues(self):
        result = generate_pr_comment(_base_data())
        assert "Passed" in result

    def test_failed_with_errors(self):
        result = generate_pr_comment(_base_data(errors=3))
        assert "Failed" in result
        assert "❌" in result

    def test_warnings_status(self):
        result = generate_pr_comment(_base_data(warnings=2))
        assert "warning" in result.lower()

    def test_prompt_count_shown(self):
        result = generate_pr_comment(_base_data(total_prompts=42))
        assert "42" in result

    def test_no_dimension_table(self):
        result = generate_pr_comment(_base_data())
        assert "Clarity" not in result


class TestWithScore:
    """When scoring is enabled (full report)."""

    def test_header_shows_score(self):
        result = generate_pr_comment(_scored_data())
        assert "72/100" in result or "73/100" in result

    def test_header_shows_tier(self):
        result = generate_pr_comment(_scored_data())
        assert "Strong" in result

    def test_dimension_table_present(self):
        result = generate_pr_comment(_scored_data())
        assert "Clarity" in result
        assert "Context" in result
        assert "Position" in result
        assert "Structure" in result
        assert "Repetition" in result

    def test_dimension_values(self):
        result = generate_pr_comment(_scored_data())
        assert "20/25" in result  # clarity 20.3 rounds to 20
        assert "18/25" in result  # context 17.8 rounds to 18
        assert "16/20" in result  # position 15.6 rounds to 16

    def test_dimension_bars(self):
        result = generate_pr_comment(_scored_data())
        assert "█" in result
        assert "░" in result

    def test_tier_distribution(self):
        result = generate_pr_comment(_scored_data())
        assert "Score distribution" in result
        assert "Expert" in result
        assert "Strong" in result

    def test_passed_with_threshold(self):
        result = generate_pr_comment(_scored_data())
        assert "threshold 50" in result
        assert "passed" in result

    def test_failed_below_threshold(self):
        data = _scored_data()
        data["score"]["pass"] = False
        data["score"]["avg_score"] = 35.0
        result = generate_pr_comment(data)
        assert "failed" in result
        assert "❌" in result


class TestSuggestions:
    def test_suggestions_section(self):
        result = generate_pr_comment(_scored_data())
        assert "Top improvements" in result
        assert "Add file path references" in result

    def test_suggestion_points(self):
        result = generate_pr_comment(_scored_data())
        assert "+6 pts" in result
        assert "+10 pts" in result

    def test_suggestion_paper_citation(self):
        result = generate_pr_comment(_scored_data())
        assert "arXiv" in result

    def test_suggestion_count(self):
        result = generate_pr_comment(_scored_data())
        assert "4 prompts" in result

    def test_no_suggestions_when_empty(self):
        data = _scored_data()
        data["score"]["top_suggestions"] = []
        result = generate_pr_comment(data)
        assert "Top improvements" not in result

    def test_total_points_in_header(self):
        result = generate_pr_comment(_scored_data())
        assert "+16 pts possible" in result  # 6 + 10


class TestViolations:
    def test_violations_collapsible(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "<details>" in result
        assert "1 violation" in result
        assert "`min-length`" in result

    def test_multiple_violations(self):
        violations = [
            {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            {
                "rule": "vague-prompt",
                "severity": "error",
                "message": "Overly vague",
                "prompt": "fix it",
            },
            {
                "rule": "short-prompt",
                "severity": "warning",
                "message": "Could be longer",
                "prompt": "fix bug",
            },
        ]
        data = _base_data(errors=2, warnings=1, violations=violations)
        result = generate_pr_comment(data)
        assert "3 violation" in result
        assert "min-length" in result
        assert "vague-prompt" in result

    def test_violations_capped_at_20(self):
        violations = [
            {"rule": f"rule-{i}", "severity": "warning", "message": f"msg {i}", "prompt": "x"}
            for i in range(25)
        ]
        data = _base_data(warnings=25, violations=violations)
        result = generate_pr_comment(data)
        assert "and 5 more" in result

    def test_no_violations_section_when_clean(self):
        result = generate_pr_comment(_base_data())
        assert "violation" not in result.lower()

    def test_error_emoji(self):
        data = _base_data(
            errors=1,
            violations=[
                {"rule": "min-length", "severity": "error", "message": "Too short", "prompt": "x"},
            ],
        )
        result = generate_pr_comment(data)
        assert "🔴" in result

    def test_warning_emoji(self):
        data = _base_data(
            warnings=1,
            violations=[
                {
                    "rule": "short-prompt",
                    "severity": "warning",
                    "message": "Short",
                    "prompt": "hi",
                },
            ],
        )
        result = generate_pr_comment(data)
        assert "🟡" in result


class TestEdgeCases:
    def test_zero_prompts(self):
        result = generate_pr_comment(_base_data(total_prompts=0))
        assert "0" in result
        assert COMMENT_MARKER in result

    def test_score_without_dimensions(self):
        """Score present but no dimension breakdown."""
        data = _base_data(
            score={
                "avg_score": 65.0,
                "min_score": 40.0,
                "max_score": 90.0,
                "threshold": 50,
                "pass": True,
            },
        )
        result = generate_pr_comment(data)
        assert "65/100" in result
        assert "Clarity" not in result  # no dimensions

    def test_score_without_threshold(self):
        """Score but threshold is 0 (no pass/fail gating)."""
        data = _base_data(
            score={
                "avg_score": 78.0,
                "min_score": 50.0,
                "max_score": 95.0,
                "threshold": 0,
                "pass": True,
                "dimensions": {
                    "clarity": {"avg": 20.0, "max": 25},
                    "context": {"avg": 18.0, "max": 25},
                    "position": {"avg": 16.0, "max": 20},
                    "structure": {"avg": 12.0, "max": 15},
                    "repetition": {"avg": 12.0, "max": 15},
                },
                "tiers": {"Expert": 0, "Strong": 5, "Good": 3, "Basic": 2, "Draft": 0},
                "top_suggestions": [],
            },
        )
        result = generate_pr_comment(data)
        assert "78/100" in result
        assert "threshold" not in result  # no threshold line

    def test_output_ends_with_newline(self):
        result = generate_pr_comment(_base_data())
        assert result.endswith("\n")

    def test_valid_markdown_tables(self):
        """Dimension table has correct column separators."""
        result = generate_pr_comment(_scored_data())
        lines = result.split("\n")
        table_lines = [line for line in lines if line.startswith("|") and "Clarity" in line]
        assert len(table_lines) == 1  # header row
        # Check alignment row follows
        idx = lines.index(table_lines[0])
        assert ":---:" in lines[idx + 1]

    def test_expert_tier_header(self):
        data = _scored_data()
        data["score"]["avg_score"] = 90.0
        result = generate_pr_comment(data)
        assert "Expert" in result

    def test_draft_tier_header(self):
        data = _scored_data()
        data["score"]["avg_score"] = 15.0
        result = generate_pr_comment(data)
        assert "Draft" in result
