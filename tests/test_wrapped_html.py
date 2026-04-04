"""Tests for the self-contained HTML share card renderer."""

from __future__ import annotations

import re

from ctxray.core.persona import PERSONAS
from ctxray.core.wrapped import WrappedReport
from ctxray.output.wrapped_html import render_wrapped_html


def _sample_report() -> WrappedReport:
    return WrappedReport(
        total_prompts=147,
        scored_prompts=120,
        avg_overall=72.3,
        top_score=94.0,
        top_task_type="debug",
        avg_scores={
            "structure": 19.5,
            "context": 23.0,
            "position": 11.6,
            "repetition": 6.3,
            "clarity": 10.2,
        },
        task_distribution={"debug": 45, "implement": 30},
        persona=PERSONAS["architect"],
    )


class TestRenderWrappedHTML:
    """Tests for render_wrapped_html()."""

    def test_returns_html_string(self) -> None:
        result = render_wrapped_html(_sample_report())
        assert "<html" in result.lower()
        assert "<!doctype html>" in result.lower()

    def test_self_contained_no_external_resources(self) -> None:
        """Only getreprompt.dev URLs are allowed; no external CSS/JS links."""
        result = render_wrapped_html(_sample_report())
        external_urls = re.findall(r"https?://[^\"\\'>\s]+", result)
        for url in external_urls:
            assert "getreprompt.dev" in url, f"Unexpected external URL: {url}"

    def test_has_inline_style_tag(self) -> None:
        result = render_wrapped_html(_sample_report())
        assert "<style>" in result.lower() or "<style " in result.lower()

    def test_contains_score(self) -> None:
        result = render_wrapped_html(_sample_report())
        assert "72" in result

    def test_contains_persona_name(self) -> None:
        result = render_wrapped_html(_sample_report())
        assert "architect" in result.lower()

    def test_contains_persona_emoji(self) -> None:
        result = render_wrapped_html(_sample_report())
        persona = PERSONAS["architect"]
        assert persona.emoji in result

    def test_contains_persona_description(self) -> None:
        result = render_wrapped_html(_sample_report())
        # The description may be HTML-escaped, so check a substring
        assert "structured" in result.lower()

    def test_contains_all_categories(self) -> None:
        result = render_wrapped_html(_sample_report())
        for category in ("Structure", "Context", "Position", "Repetition", "Clarity"):
            assert category in result, f"Missing category: {category}"

    def test_contains_stats_row(self) -> None:
        result = render_wrapped_html(_sample_report())
        assert "147" in result  # total_prompts
        assert "94" in result  # top_score
        assert "debug" in result.lower()  # top_task_type

    def test_contains_persona_traits(self) -> None:
        result = render_wrapped_html(_sample_report())
        persona = PERSONAS["architect"]
        for trait in persona.traits:
            assert trait in result or trait.lower() in result.lower()

    def test_contains_footer_link(self) -> None:
        result = render_wrapped_html(_sample_report())
        assert "getreprompt.dev" in result
        assert "ctxray" in result.lower()

    def test_score_color_green_for_72(self) -> None:
        """72.3% should use green (#00C853)."""
        result = render_wrapped_html(_sample_report())
        assert "#00C853" in result or "#00c853" in result.lower()

    def test_score_color_purple_for_high(self) -> None:
        report = _sample_report()
        report = WrappedReport(
            total_prompts=report.total_prompts,
            scored_prompts=report.scored_prompts,
            avg_overall=90.0,
            top_score=report.top_score,
            top_task_type=report.top_task_type,
            avg_scores=report.avg_scores,
            task_distribution=report.task_distribution,
            persona=report.persona,
        )
        result = render_wrapped_html(report)
        assert "#7C4DFF" in result or "#7c4dff" in result.lower()

    def test_score_color_yellow_for_mid(self) -> None:
        report = WrappedReport(avg_overall=55.0)
        result = render_wrapped_html(report)
        assert "#FFD700" in result or "#ffd700" in result.lower()

    def test_score_color_orange_for_low(self) -> None:
        report = WrappedReport(avg_overall=35.0)
        result = render_wrapped_html(report)
        assert "#FF8C00" in result or "#ff8c00" in result.lower()

    def test_score_color_red_for_very_low(self) -> None:
        report = WrappedReport(avg_overall=15.0)
        result = render_wrapped_html(report)
        assert "#FF4444" in result or "#ff4444" in result.lower()

    def test_empty_report_returns_valid_html(self) -> None:
        """Default WrappedReport() should still produce valid HTML."""
        report = WrappedReport()
        result = render_wrapped_html(report)
        assert "<!doctype html>" in result.lower()
        assert "<html" in result.lower()
        assert "</html>" in result.lower()

    def test_html_escaping_xss(self) -> None:
        """User-derived text must be escaped to prevent XSS."""
        malicious = PERSONAS["explorer"]
        # Create a report with XSS in top_task_type
        report = WrappedReport(
            top_task_type='<script>alert("xss")</script>',
            persona=malicious,
        )
        result = render_wrapped_html(report)
        assert "<script>alert" not in result
        assert "&lt;script&gt;" in result

    def test_dark_theme_colors_present(self) -> None:
        result = render_wrapped_html(_sample_report())
        # Check dark theme background color is present
        assert "#0d1117" in result.lower()

    def test_category_bars_have_percentages(self) -> None:
        """Score breakdown bars should reflect percentage values."""
        result = render_wrapped_html(_sample_report())
        # structure: 19.5/25 = 78%, context: 23/25 = 92%
        # The bars should have width percentages
        assert "width:" in result.lower() or "width :" in result.lower()
