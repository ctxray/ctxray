# tests/test_insights.py
"""Tests for the personal insights engine."""

from __future__ import annotations

from reprompt.core.insights import compute_insights


class TestComputeInsights:
    """Test insights generation from stored features."""

    def test_empty_features(self):
        result = compute_insights([])
        assert result["prompt_count"] == 0
        assert result["insights"] == []

    def test_single_prompt(self):
        features = [
            {
                "prompt_hash": "h1",
                "task_type": "debug",
                "word_count": 50,
                "overall_score": 60.0,
                "key_instruction_position": 0.1,
                "keyword_repetition_freq": 0.0,
                "context_specificity": 0.3,
                "has_constraints": False,
                "constraint_count": 0,
                "ambiguity_score": 0.2,
                "has_code_blocks": False,
                "has_file_references": True,
                "has_error_messages": False,
            }
        ]
        result = compute_insights(features)
        assert result["prompt_count"] == 1
        assert result["avg_score"] == 60.0

    def test_position_insight_generated(self):
        # Most prompts have mid-buried instructions
        features = [
            {
                "prompt_hash": f"h{i}",
                "task_type": "debug",
                "overall_score": 40.0,
                "key_instruction_position": 0.5,
                "keyword_repetition_freq": 0.0,
                "context_specificity": 0.3,
                "has_constraints": False,
                "constraint_count": 0,
                "ambiguity_score": 0.2,
                "word_count": 50,
                "has_code_blocks": False,
                "has_file_references": False,
                "has_error_messages": False,
            }
            for i in range(20)
        ]
        result = compute_insights(features)
        insight_categories = [i["category"] for i in result["insights"]]
        assert "position" in insight_categories

    def test_best_and_worst_task_types(self):
        features = [
            {
                "prompt_hash": "d1",
                "task_type": "debug",
                "overall_score": 80.0,
                "key_instruction_position": 0.1,
                "keyword_repetition_freq": 0.3,
                "context_specificity": 0.7,
                "has_constraints": True,
                "constraint_count": 2,
                "ambiguity_score": 0.1,
                "word_count": 60,
                "has_code_blocks": True,
                "has_file_references": True,
                "has_error_messages": True,
            },
            {
                "prompt_hash": "i1",
                "task_type": "implement",
                "overall_score": 30.0,
                "key_instruction_position": 0.5,
                "keyword_repetition_freq": 0.0,
                "context_specificity": 0.1,
                "has_constraints": False,
                "constraint_count": 0,
                "ambiguity_score": 0.5,
                "word_count": 10,
                "has_code_blocks": False,
                "has_file_references": False,
                "has_error_messages": False,
            },
        ]
        result = compute_insights(features)
        assert result["best_task_type"]["type"] == "debug"
        assert result["worst_task_type"]["type"] == "implement"
