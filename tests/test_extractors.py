# tests/test_extractors.py
"""Tests for Tier 1 feature extractors."""
from __future__ import annotations

from reprompt.core.extractors import extract_features


class TestBasicMetrics:
    """Test basic counting features."""

    def test_word_count(self):
        dna = extract_features("Fix the bug in auth.py", source="test", session_id="s1")
        assert dna.word_count == 6

    def test_line_count_single(self):
        dna = extract_features("Fix the bug", source="test", session_id="s1")
        assert dna.line_count == 1

    def test_line_count_multi(self):
        dna = extract_features("Line one\nLine two\nLine three", source="test", session_id="s1")
        assert dna.line_count == 3

    def test_sentence_count(self):
        dna = extract_features(
            "Fix the bug. Then add tests. Deploy it.",
            source="test", session_id="s1",
        )
        assert dna.sentence_count == 3

    def test_empty_prompt(self):
        dna = extract_features("", source="test", session_id="s1")
        assert dna.word_count == 0
        assert dna.overall_score == 0.0


class TestStructureDetection:
    """Test prompt structure feature extraction."""

    def test_role_definition_detected(self):
        dna = extract_features(
            "You are a senior Python developer.\n\nFix the auth bug.",
            source="test", session_id="s1",
        )
        assert dna.has_role_definition is True

    def test_role_definition_absent(self):
        dna = extract_features("Fix the auth bug.", source="test", session_id="s1")
        assert dna.has_role_definition is False

    def test_constraints_detected(self):
        dna = extract_features(
            "Add a login endpoint. Do not modify existing routes. Must return 201.",
            source="test", session_id="s1",
        )
        assert dna.has_constraints is True
        assert dna.constraint_count >= 2

    def test_examples_detected(self):
        text = """Convert dates.

Example:
Input: "March 5"
Output: "2026-03-05"
"""
        dna = extract_features(text, source="test", session_id="s1")
        assert dna.has_examples is True

    def test_output_format_detected(self):
        dna = extract_features(
            "List all endpoints. Return as JSON with fields: path, method.",
            source="test", session_id="s1",
        )
        assert dna.has_output_format is True

    def test_step_by_step_detected(self):
        dna = extract_features(
            "Think step by step about how to refactor this function.",
            source="test", session_id="s1",
        )
        assert dna.has_step_by_step is True

    def test_code_blocks_detected(self):
        text = "Fix this:\n\n```python\ndef foo():\n    pass\n```"
        dna = extract_features(text, source="test", session_id="s1")
        assert dna.has_code_blocks is True
        assert dna.code_block_count == 1

    def test_multiple_code_blocks(self):
        text = "Compare:\n\n```\nold code\n```\n\nWith:\n\n```\nnew code\n```"
        dna = extract_features(text, source="test", session_id="s1")
        assert dna.code_block_count == 2

    def test_file_references_detected(self):
        dna = extract_features(
            "Fix the bug in src/auth/login.py at line 42",
            source="test", session_id="s1",
        )
        assert dna.has_file_references is True
        assert dna.file_reference_count >= 1

    def test_error_messages_detected(self):
        dna = extract_features(
            "Fix this error: TypeError: cannot read property 'name' of undefined",
            source="test", session_id="s1",
        )
        assert dna.has_error_messages is True

    def test_section_count(self):
        text = "## Context\nSome context.\n\n## Task\nDo something.\n\n## Constraints\nDon't break."
        dna = extract_features(text, source="test", session_id="s1")
        assert dna.section_count == 3


class TestResearchBackedFeatures:
    """Test features derived from research papers."""

    def test_keyword_repetition_detected(self):
        # "authentication" appears twice — repetition should be > 0
        dna = extract_features(
            "Fix the authentication bug in login.py. "
            "The authentication system fails on expired tokens.",
            source="test", session_id="s1",
        )
        assert dna.keyword_repetition_freq > 0.0

    def test_no_repetition(self):
        dna = extract_features("Fix the bug.", source="test", session_id="s1")
        assert dna.keyword_repetition_freq == 0.0

    def test_instruction_at_start(self):
        # Key instruction at the start → position near 0.0
        dna = extract_features(
            "Fix the auth bug.\n\nHere is the context:\n```\nsome code\n```",
            source="test", session_id="s1",
        )
        assert dna.key_instruction_position < 0.3

    def test_instruction_at_end(self):
        # Context first, instruction last
        dna = extract_features(
            "Here is the code:\n```\nsome code\n```\n\nFix the auth bug in this code.",
            source="test", session_id="s1",
        )
        assert dna.key_instruction_position > 0.5

    def test_opening_quality_good(self):
        # Starts with specific instruction
        dna = extract_features(
            "Fix the TypeError in auth/login.py:42 when token expires.",
            source="test", session_id="s1",
        )
        assert dna.opening_quality > 0.5

    def test_opening_quality_bad(self):
        # Starts vaguely
        dna = extract_features("Help me with something.", source="test", session_id="s1")
        assert dna.opening_quality < 0.5


class TestTaskTypeClassification:
    """Test keyword-based task type classification."""

    def test_debug_task(self):
        dna = extract_features("Debug the auth error in login.py", source="test", session_id="s1")
        assert dna.task_type == "debug"

    def test_implement_task(self):
        dna = extract_features("Add a new REST endpoint for users", source="test", session_id="s1")
        assert dna.task_type == "implement"

    def test_refactor_task(self):
        dna = extract_features(
            "Refactor the payment service to use strategy pattern",
            source="test", session_id="s1",
        )
        assert dna.task_type == "refactor"

    def test_explain_task(self):
        dna = extract_features(
            "Explain how the auth middleware works",
            source="test", session_id="s1",
        )
        assert dna.task_type == "explain"

    def test_test_task(self):
        dna = extract_features(
            "Add unit tests for the UserService class",
            source="test", session_id="s1",
        )
        assert dna.task_type == "test"

    def test_unknown_task(self):
        dna = extract_features("Hello world", source="test", session_id="s1")
        assert dna.task_type == "other"


class TestAmbiguityDetection:
    """Test ambiguity scoring."""

    def test_vague_prompt_high_ambiguity(self):
        dna = extract_features("Fix it somehow maybe", source="test", session_id="s1")
        assert dna.ambiguity_score > 0.3

    def test_specific_prompt_low_ambiguity(self):
        dna = extract_features(
            "Fix the TypeError in auth/login.py:42 — the validate_token function "
            "raises when token.expiry is None. Add a None check before the comparison.",
            source="test", session_id="s1",
        )
        assert dna.ambiguity_score < 0.3


class TestContextSpecificity:
    """Test context specificity scoring."""

    def test_high_specificity(self):
        text = (
            "Fix the TypeError in src/auth/login.py:42.\n"
            "Error: TypeError: cannot read property 'expiry' of None\n"
            "```python\ndef validate_token(token):\n    if token.expiry < now():\n```"
        )
        dna = extract_features(text, source="test", session_id="s1")
        assert dna.context_specificity > 0.5

    def test_low_specificity(self):
        dna = extract_features("Fix the bug", source="test", session_id="s1")
        assert dna.context_specificity < 0.3
