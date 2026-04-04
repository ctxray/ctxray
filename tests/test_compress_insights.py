"""Tests for compressibility integration into insights engine."""

from ctxray.core.insights import OPTIMAL, compute_insights


def test_optimal_has_compressibility():
    assert "compressibility" in OPTIMAL


def test_compressibility_insight_generated():
    features = [
        {
            "compressibility": 0.35,
            "overall_score": 50.0,
            "task_type": "code_generation",
            "context_specificity": 0.5,
            "keyword_repetition_freq": 0.2,
            "ambiguity_score": 0.1,
            "has_constraints": True,
            "source": "claude_code",
            "key_instruction_position": 0.1,
        },
    ] * 10
    result = compute_insights(features)
    categories = [i["category"] for i in result["insights"]]
    assert "verbosity" in categories


def test_no_compressibility_insight_when_low():
    features = [
        {
            "compressibility": 0.05,
            "overall_score": 80.0,
            "task_type": "code_generation",
            "context_specificity": 0.7,
            "keyword_repetition_freq": 0.3,
            "ambiguity_score": 0.1,
            "has_constraints": True,
            "source": "claude_code",
            "key_instruction_position": 0.1,
        },
    ] * 10
    result = compute_insights(features)
    categories = [i["category"] for i in result["insights"]]
    assert "verbosity" not in categories


def test_compressibility_insight_not_generated_with_few_prompts():
    """Should not generate insight when fewer than 5 prompts."""
    features = [
        {
            "compressibility": 0.35,
            "overall_score": 50.0,
            "task_type": "code_generation",
            "context_specificity": 0.5,
            "keyword_repetition_freq": 0.2,
            "ambiguity_score": 0.1,
            "has_constraints": True,
            "source": "claude_code",
            "key_instruction_position": 0.1,
        },
    ] * 3
    result = compute_insights(features)
    categories = [i["category"] for i in result["insights"]]
    assert "verbosity" not in categories


def test_compressibility_insight_has_correct_fields():
    features = [
        {
            "compressibility": 0.40,
            "overall_score": 50.0,
            "task_type": "code_generation",
            "context_specificity": 0.5,
            "keyword_repetition_freq": 0.2,
            "ambiguity_score": 0.1,
            "has_constraints": True,
            "source": "claude_code",
            "key_instruction_position": 0.1,
        },
    ] * 10
    result = compute_insights(features)
    verbosity_insights = [i for i in result["insights"] if i["category"] == "verbosity"]
    assert len(verbosity_insights) == 1
    insight = verbosity_insights[0]
    assert "finding" in insight
    assert "optimal" in insight
    assert "action" in insight
    assert insight["impact"] == "medium"
