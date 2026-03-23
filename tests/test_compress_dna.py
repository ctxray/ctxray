"""Tests for compressibility integration into PromptDNA and extractors."""

from reprompt.core.extractors import extract_features
from reprompt.core.prompt_dna import PromptDNA


def test_prompt_dna_has_compressibility():
    dna = PromptDNA(prompt_hash="test", source="test", task_type="test")
    assert hasattr(dna, "compressibility")
    assert dna.compressibility == 0.0


def test_compressibility_in_feature_vector():
    dna = PromptDNA(prompt_hash="test", source="test", task_type="test", compressibility=0.25)
    vec = dna.feature_vector()
    assert 0.25 in vec


def test_compressibility_in_to_dict():
    dna = PromptDNA(prompt_hash="test", source="test", task_type="test", compressibility=0.3)
    d = dna.to_dict()
    assert d["compressibility"] == 0.3


def test_extract_features_computes_compressibility_zh():
    text = "嗯，帮我看看这个文件的时候检查一下错误"
    dna = extract_features(text, source="test", session_id="test")
    assert dna.compressibility > 0.0
    assert dna.compressibility <= 1.0


def test_extract_features_computes_compressibility_en():
    text = "Could you please basically check the error handling in this file"
    dna = extract_features(text, source="test", session_id="test")
    assert dna.compressibility > 0.0
    assert dna.compressibility <= 1.0


def test_clean_prompt_low_compressibility():
    text = "Check error handling in compress.py line 42"
    dna = extract_features(text, source="test", session_id="test")
    assert dna.compressibility < 0.3


def test_feature_vector_length_consistent():
    from dataclasses import fields as dc_fields

    dna = PromptDNA(prompt_hash="test", source="test", task_type="test")
    vec = dna.feature_vector()
    numeric_count = sum(
        1 for f in dc_fields(dna) if isinstance(getattr(dna, f.name), (int, float, bool))
    )
    assert len(vec) == numeric_count
