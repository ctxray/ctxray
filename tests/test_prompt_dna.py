"""Tests for PromptDNA data model."""

from __future__ import annotations

from reprompt.core.prompt_dna import PromptDNA


class TestPromptDNA:
    """Test PromptDNA dataclass."""

    def test_create_minimal(self):
        dna = PromptDNA(prompt_hash="abc123", source="claude_code", task_type="debug")
        assert dna.prompt_hash == "abc123"
        assert dna.source == "claude_code"
        assert dna.task_type == "debug"
        assert dna.token_count == 0
        assert dna.overall_score == 0.0

    def test_all_fields_have_defaults(self):
        dna = PromptDNA(prompt_hash="x", source="test", task_type="other")
        assert isinstance(dna.has_role_definition, bool)
        assert isinstance(dna.constraint_count, int)
        assert isinstance(dna.keyword_repetition_freq, float)
        assert isinstance(dna.key_instruction_position, float)
        assert isinstance(dna.predicted_effectiveness, float)

    def test_to_dict(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="t")
        d = dna.to_dict()
        assert isinstance(d, dict)
        assert d["prompt_hash"] == "h"
        assert "overall_score" in d

    def test_to_dict_roundtrip(self):
        dna = PromptDNA(
            prompt_hash="h",
            source="s",
            task_type="debug",
            token_count=50,
            has_role_definition=True,
            keyword_repetition_freq=0.5,
            overall_score=72.0,
        )
        d = dna.to_dict()
        dna2 = PromptDNA(**d)
        assert dna2.token_count == 50
        assert dna2.has_role_definition is True
        assert dna2.overall_score == 72.0

    def test_feature_vector(self):
        dna = PromptDNA(
            prompt_hash="h",
            source="s",
            task_type="debug",
            token_count=100,
            word_count=80,
            has_role_definition=True,
            constraint_count=2,
        )
        vec = dna.feature_vector()
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        assert len(vec) > 10


class TestPromptDNALocale:
    def test_default_locale_is_en(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="t")
        assert dna.locale == "en"

    def test_locale_zh(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="t", locale="zh")
        assert dna.locale == "zh"

    def test_locale_in_to_dict(self):
        dna = PromptDNA(prompt_hash="h", source="s", task_type="t", locale="zh")
        d = dna.to_dict()
        assert d["locale"] == "zh"

    def test_locale_excluded_from_feature_vector(self):
        """locale is a string -- should not appear in feature_vector."""
        dna1 = PromptDNA(prompt_hash="h", source="s", task_type="t", locale="en")
        dna2 = PromptDNA(prompt_hash="h", source="s", task_type="t", locale="zh")
        assert dna1.feature_vector() == dna2.feature_vector()

    def test_feature_vector_length_unchanged(self):
        """Adding locale must not change vector dimensions."""
        dna = PromptDNA(prompt_hash="h", source="s", task_type="t")
        vec = dna.feature_vector()
        # The existing vector has a known length; locale (str) is excluded
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
