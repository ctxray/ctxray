"""Tests for Unicode-range language detection."""

from __future__ import annotations

from reprompt.core.lang_detect import LanguageInfo, detect_prompt_language


class TestDetectLanguage:
    """Test dominant language detection from Unicode ranges."""

    def test_pure_english(self):
        result = detect_prompt_language("Fix the bug in auth.py")
        assert result.lang == "en"
        assert result.confidence > 0.8

    def test_pure_chinese(self):
        result = detect_prompt_language("修复认证模块中的错误")
        assert result.lang == "zh"
        assert result.confidence > 0.8

    def test_mixed_chinese_dominant(self):
        result = detect_prompt_language("修复 auth.py 中的认证错误，不要修改现有的测试")
        assert result.lang == "zh"

    def test_mixed_english_dominant(self):
        result = detect_prompt_language(
            "Fix the authentication bug in the 认证 module, don't modify tests"
        )
        assert result.lang == "en"

    def test_japanese(self):
        result = detect_prompt_language("認証モジュールのバグを修正してください")
        assert result.lang == "ja"

    def test_korean(self):
        result = detect_prompt_language("인증 모듈의 버그를 수정하세요")
        assert result.lang == "ko"

    def test_empty_string(self):
        result = detect_prompt_language("")
        assert result.lang == "en"  # default fallback
        assert result.confidence == 0.0

    def test_whitespace_only(self):
        result = detect_prompt_language("   \n\t  ")
        assert result.lang == "en"
        assert result.confidence == 0.0

    def test_code_only(self):
        """Code blocks should not affect language detection."""
        result = detect_prompt_language("```python\ndef foo():\n    pass\n```")
        assert result.lang == "en"

    def test_chinese_with_code(self):
        text = "请修复这个函数\n```python\ndef foo():\n    pass\n```\n确保测试通过"
        result = detect_prompt_language(text)
        assert result.lang == "zh"

    def test_numbers_and_symbols_ignored(self):
        result = detect_prompt_language("12345 !@#$% 67890")
        assert result.lang == "en"  # default when no script detected
        assert result.confidence == 0.0


class TestLanguageInfo:
    def test_dataclass_fields(self):
        info = LanguageInfo(lang="zh", confidence=0.9, script_ratios={"cjk": 0.9})
        assert info.lang == "zh"
        assert info.confidence == 0.9
        assert "cjk" in info.script_ratios

    def test_is_cjk(self):
        info = LanguageInfo(lang="zh", confidence=0.9, script_ratios={})
        assert info.is_cjk is True
        info_en = LanguageInfo(lang="en", confidence=0.9, script_ratios={})
        assert info_en.is_cjk is False
