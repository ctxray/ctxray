"""Tests for ctxray public API."""

from __future__ import annotations


def test_public_api_score_prompt():
    """Public API score_prompt returns expected keys."""
    from ctxray import score_prompt

    result = score_prompt("Refactor the authentication module to use dependency injection")
    assert "total" in result
    assert "dimensions" in result
    assert "grade" in result
    assert 0 <= result["total"] <= 100


def test_public_api_compare_prompts():
    """Public API compare_prompts returns winner."""
    from ctxray import compare_prompts

    result = compare_prompts(
        "fix bug",
        "Refactor the authentication module to use dependency injection for better testability",
    )
    assert result["winner"] in ("a", "b")


def test_public_api_extract_features():
    """Public API extract_features returns PromptDNA."""
    from ctxray import extract_features

    dna = extract_features("Add comprehensive error handling to the API endpoints")
    assert hasattr(dna, "overall_score")
