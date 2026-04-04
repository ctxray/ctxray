# tests/test_extractors_routing.py
"""Tests for language-aware extractor routing."""

from __future__ import annotations

from ctxray.core.extractors import extract_features


class TestExtractorRouting:
    """Test that extract_features routes to correct locale extractor."""

    def test_english_prompt_routes_to_en(self):
        dna = extract_features("Fix the bug in auth.py", source="test", session_id="s1")
        assert dna.locale == "en"

    def test_chinese_prompt_routes_to_zh(self):
        dna = extract_features("修复认证模块中的错误", source="test", session_id="s1")
        assert dna.locale == "zh"

    def test_chinese_with_code_routes_to_zh(self):
        text = "修复这个函数\n```python\ndef foo():\n    pass\n```\n确保测试通过"
        dna = extract_features(text, source="test", session_id="s1")
        assert dna.locale == "zh"
        assert dna.has_code_blocks is True

    def test_mixed_chinese_dominant_routes_to_zh(self):
        dna = extract_features(
            "修复 auth.py 中的认证错误，不要修改现有的测试文件",
            source="test",
            session_id="s1",
        )
        assert dna.locale == "zh"

    def test_english_still_works_unchanged(self):
        """Existing English extraction must not regress."""
        dna = extract_features(
            "You are a senior Python developer.\n\nFix the auth bug. Do not modify tests.",
            source="test",
            session_id="s1",
        )
        assert dna.locale == "en"
        assert dna.has_role_definition is True
        assert dna.has_constraints is True

    def test_chinese_role_detected_via_router(self):
        dna = extract_features(
            "你是一个资深Python开发者。\n\n修复认证错误。",
            source="test",
            session_id="s1",
        )
        assert dna.locale == "zh"
        assert dna.has_role_definition is True

    def test_chinese_constraints_via_router(self):
        dna = extract_features(
            "添加登录接口。不要修改路由。必须返回201。",
            source="test",
            session_id="s1",
        )
        assert dna.locale == "zh"
        assert dna.has_constraints is True
        assert dna.constraint_count >= 2

    def test_empty_prompt_defaults_to_en(self):
        dna = extract_features("", source="test", session_id="s1")
        assert dna.locale == "en"

    def test_feature_vector_same_dimensions(self):
        """English and Chinese must produce same vector length."""
        en = extract_features("Fix the bug in auth.py", source="test", session_id="s1")
        zh = extract_features("修复认证模块中的错误", source="test", session_id="s1")
        assert len(en.feature_vector()) == len(zh.feature_vector())

    def test_same_prompt_hash_for_identical_content(self):
        """Hash is computed on the stripped text, not affected by routing."""
        dna1 = extract_features("修复错误", source="test", session_id="s1")
        dna2 = extract_features("修复错误", source="test", session_id="s1")
        assert dna1.prompt_hash == dna2.prompt_hash
