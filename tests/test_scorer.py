# tests/test_scorer.py
"""Tests for the prompt scoring engine."""
from __future__ import annotations

import pytest

from reprompt.core.prompt_dna import PromptDNA
from reprompt.core.scorer import score_prompt, ScoreBreakdown


class TestScorePrompt:
    """Test the weighted scoring engine."""

    def test_returns_score_breakdown(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="debug")
        result = score_prompt(dna)
        assert isinstance(result, ScoreBreakdown)
        assert 0 <= result.total <= 100

    def test_minimal_prompt_scores_low(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="other", word_count=2)
        result = score_prompt(dna)
        assert result.total < 30

    def test_well_structured_prompt_scores_high(self):
        dna = PromptDNA(
            prompt_hash="h", source="s", task_type="debug",
            word_count=50, sentence_count=3,
            has_role_definition=True,
            has_constraints=True, constraint_count=2,
            has_code_blocks=True, code_block_count=1,
            has_file_references=True, file_reference_count=2,
            has_error_messages=True,
            key_instruction_position=0.1,  # front-loaded (good)
            keyword_repetition_freq=0.3,
            opening_quality=0.8,
            context_specificity=0.7,
            ambiguity_score=0.1,
        )
        result = score_prompt(dna)
        assert result.total > 70

    def test_middle_buried_instruction_penalty(self):
        good = PromptDNA(
            prompt_hash="h", source="s", task_type="debug",
            word_count=50, key_instruction_position=0.1,
        )
        bad = PromptDNA(
            prompt_hash="h", source="s", task_type="debug",
            word_count=50, key_instruction_position=0.5,
        )
        good_score = score_prompt(good)
        bad_score = score_prompt(bad)
        assert good_score.position > bad_score.position

    def test_repetition_bonus(self):
        no_rep = PromptDNA(
            prompt_hash="h", source="s", task_type="debug",
            word_count=50, keyword_repetition_freq=0.0,
        )
        has_rep = PromptDNA(
            prompt_hash="h", source="s", task_type="debug",
            word_count=50, keyword_repetition_freq=0.5,
        )
        assert score_prompt(has_rep).repetition > score_prompt(no_rep).repetition

    def test_score_breakdown_categories(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="debug", word_count=50)
        result = score_prompt(dna)
        # All category scores should exist and be non-negative
        assert result.structure >= 0
        assert result.context >= 0
        assert result.position >= 0
        assert result.repetition >= 0
        assert result.clarity >= 0

    def test_suggestions_for_low_score(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="debug", word_count=3)
        result = score_prompt(dna)
        assert len(result.suggestions) > 0

    def test_high_score_prompt_few_suggestions(self):
        dna = PromptDNA(
            prompt_hash="h", source="s", task_type="debug",
            word_count=80, sentence_count=4,
            has_role_definition=True,
            has_constraints=True, constraint_count=3,
            has_examples=True, example_count=1,
            has_output_format=True,
            has_code_blocks=True, code_block_count=1,
            has_file_references=True, file_reference_count=2,
            has_error_messages=True,
            key_instruction_position=0.05,
            keyword_repetition_freq=0.4,
            opening_quality=0.9,
            context_specificity=0.8,
            ambiguity_score=0.05,
        )
        result = score_prompt(dna)
        assert result.total > 80
        # Well-constructed prompts should have very few suggestions
        assert len(result.suggestions) <= 1
