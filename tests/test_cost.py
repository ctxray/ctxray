"""Tests for token cost estimation."""

from ctxray.core.cost import (
    estimate_cost,
    estimate_tokens,
    format_cost,
    model_for_source,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_whitespace_only(self):
        assert estimate_tokens("   ") == 0

    def test_english_words(self):
        # "Fix the auth bug" = 4 words * 1.3 ≈ 5 tokens
        result = estimate_tokens("Fix the auth bug", locale="en")
        assert result == 5

    def test_single_word(self):
        result = estimate_tokens("Hello", locale="en")
        assert result >= 1

    def test_chinese_text(self):
        # Chinese: character count * 1.5
        result = estimate_tokens("修复认证模块的错误", locale="zh")
        assert result > 0
        # 9 CJK chars * 1.5 ≈ 13-14
        assert result >= 10

    def test_mixed_cjk_detected(self):
        # Mixed text with >30% CJK should use CJK counting
        result = estimate_tokens("修复这个认证bug在login.ts里面", locale="en")
        assert result > 0

    def test_long_english_text(self):
        text = "word " * 100  # 100 words
        result = estimate_tokens(text.strip(), locale="en")
        assert 120 <= result <= 140  # 100 * 1.3 = 130


class TestEstimateCost:
    def test_claude_code_cost(self):
        # 1000 tokens at claude-sonnet ($3/1M) = $0.003
        cost = estimate_cost(1000, source="claude-code")
        assert abs(cost - 0.003) < 0.0001

    def test_cursor_cost(self):
        # 1000 tokens at gpt-4o ($2.50/1M) = $0.0025
        cost = estimate_cost(1000, source="cursor")
        assert abs(cost - 0.0025) < 0.0001

    def test_zero_tokens(self):
        assert estimate_cost(0, source="claude-code") == 0.0

    def test_unknown_source_defaults_to_sonnet(self):
        cost = estimate_cost(1000, source="unknown-tool")
        assert abs(cost - 0.003) < 0.0001


class TestFormatCost:
    def test_zero(self):
        assert format_cost(0) == "$0.00"

    def test_small_cost(self):
        # < $0.01 should show 4 decimal places
        result = format_cost(0.003)
        assert result == "$0.0030"

    def test_medium_cost(self):
        result = format_cost(0.15)
        assert result == "$0.150"

    def test_large_cost(self):
        result = format_cost(2.50)
        assert result == "$2.50"


class TestModelForSource:
    def test_claude_code(self):
        assert model_for_source("claude-code") == "claude-sonnet"

    def test_cursor(self):
        assert model_for_source("cursor") == "gpt-4o"

    def test_gemini(self):
        assert model_for_source("gemini") == "gemini-2.0-flash"

    def test_unknown(self):
        assert model_for_source("unknown") == "claude-sonnet"
