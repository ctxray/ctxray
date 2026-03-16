"""Tests for the Rich terminal wrapped report renderer."""

from __future__ import annotations

from reprompt.core.persona import PERSONAS
from reprompt.core.wrapped import WrappedReport
from reprompt.output.wrapped_terminal import render_wrapped


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
        task_distribution={
            "debug": 45,
            "implement": 30,
            "refactor": 20,
            "explain": 15,
            "other": 10,
        },
        persona=PERSONAS["architect"],
    )


class TestRenderWrapped:
    def test_returns_string(self) -> None:
        result = render_wrapped(_sample_report())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_score(self) -> None:
        result = render_wrapped(_sample_report())
        assert "72" in result

    def test_contains_persona(self) -> None:
        result = render_wrapped(_sample_report())
        # Persona name is lowercase "architect" in the data model
        assert "architect" in result.lower()

    def test_contains_categories(self) -> None:
        result = render_wrapped(_sample_report())
        for cat in ("Structure", "Context", "Position", "Repetition", "Clarity"):
            assert cat in result, f"Missing category: {cat}"

    def test_contains_prompt_count(self) -> None:
        result = render_wrapped(_sample_report())
        assert "147" in result

    def test_contains_top_score(self) -> None:
        result = render_wrapped(_sample_report())
        assert "94" in result

    def test_contains_task_type(self) -> None:
        result = render_wrapped(_sample_report())
        assert "debug" in result.lower()

    def test_contains_persona_traits(self) -> None:
        result = render_wrapped(_sample_report())
        # At least 1 of the architect's traits should appear
        traits_found = sum(1 for t in PERSONAS["architect"].traits if t in result)
        assert traits_found >= 1, "Expected at least one persona trait in output"

    def test_contains_task_distribution(self) -> None:
        result = render_wrapped(_sample_report())
        # Top 3 by count: debug(45), implement(30), refactor(20)
        assert "debug" in result.lower()
        assert "implement" in result.lower()

    def test_empty_report(self) -> None:
        """A default WrappedReport (no scored prompts) should still render."""
        report = WrappedReport()
        result = render_wrapped(report)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should tell user to run scan first
        assert "scan" in result.lower()

    def test_score_breakdown_bars(self) -> None:
        """Score breakdown should show percentage-style bars."""
        result = render_wrapped(_sample_report())
        # Structure is 19.5/25 = 78%, should show a bar
        # We just check the raw score or percentage appears
        assert "19.5" in result or "78" in result

    def test_header_panel(self) -> None:
        result = render_wrapped(_sample_report())
        assert "Prompt DNA" in result
