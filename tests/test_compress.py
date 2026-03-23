"""Tests for reprompt.core.compress — CompressResult + protected zones."""

from __future__ import annotations

from reprompt.core.compress import CompressResult, compress_text


class TestCompressResult:
    """CompressResult dataclass and basic contract."""

    def test_returns_dataclass(self):
        result = compress_text("hello world")
        assert isinstance(result, CompressResult)
        assert result.original == "hello world"
        assert isinstance(result.savings_pct, float)
        assert isinstance(result.changes, list)

    def test_has_token_counts(self):
        result = compress_text("hello world")
        assert isinstance(result.original_tokens, int)
        assert isinstance(result.compressed_tokens, int)
        assert result.original_tokens > 0

    def test_has_language(self):
        result = compress_text("hello world")
        assert isinstance(result.language, str)
        assert result.language == "en"

    def test_empty_input(self):
        result = compress_text("")
        assert result.compressed == ""
        assert result.savings_pct == 0.0
        assert result.original_tokens == 0
        assert result.compressed_tokens == 0

    def test_compressed_field_present(self):
        result = compress_text("please help me with this task")
        assert isinstance(result.compressed, str)
        assert len(result.compressed) > 0


class TestProtectedZonesCodeBlocks:
    """Code blocks must survive compression unchanged."""

    def test_pure_code_not_compressed(self):
        code = "```python\ndef foo():\n    return bar\n```"
        result = compress_text(code)
        assert "def foo():" in result.compressed
        assert "return bar" in result.compressed

    def test_code_block_with_surrounding_text(self):
        text = "basically run this:\n```bash\npytest tests/ -v\n```\nto test"
        result = compress_text(text)
        assert "```bash\npytest tests/ -v\n```" in result.compressed

    def test_multiple_code_blocks(self):
        text = "first:\n```python\nx = 1\n```\nsecond:\n```js\ny = 2\n```"
        result = compress_text(text)
        assert "```python\nx = 1\n```" in result.compressed
        assert "```js\ny = 2\n```" in result.compressed


class TestProtectedZonesURLs:
    """URLs must survive compression unchanged."""

    def test_url_not_compressed(self):
        text = "basically check https://example.com/path for details"
        result = compress_text(text)
        assert "https://example.com/path" in result.compressed

    def test_http_url_not_compressed(self):
        text = "see http://localhost:8000/api/health for status"
        result = compress_text(text)
        assert "http://localhost:8000/api/health" in result.compressed

    def test_url_with_query_params(self):
        text = "go to https://example.com/search?q=test&page=2 now"
        result = compress_text(text)
        assert "https://example.com/search?q=test&page=2" in result.compressed


class TestProtectedZonesFilePaths:
    """File paths must survive compression unchanged."""

    def test_file_path_not_compressed(self):
        text = "basically look at src/reprompt/core/compress.py"
        result = compress_text(text)
        assert "src/reprompt/core/compress.py" in result.compressed

    def test_relative_dot_path(self):
        text = "check ./tests/test_compress.py for examples"
        result = compress_text(text)
        assert "./tests/test_compress.py" in result.compressed

    def test_absolute_path(self):
        text = "the config is at /etc/nginx/nginx.conf"
        result = compress_text(text)
        assert "/etc/nginx/nginx.conf" in result.compressed

    def test_home_tilde_path(self):
        text = "look at ~/projects/reprompt/src/cli.py"
        result = compress_text(text)
        assert "~/projects/reprompt/src/cli.py" in result.compressed


class TestProtectedZonesInlineCode:
    """Inline code must survive compression unchanged."""

    def test_inline_code_not_compressed(self):
        text = "basically run `pytest tests/ -v` to test"
        result = compress_text(text)
        assert "`pytest tests/ -v`" in result.compressed

    def test_multiple_inline_code(self):
        text = "use `git add .` then `git commit -m 'msg'` to save"
        result = compress_text(text)
        assert "`git add .`" in result.compressed
        assert "`git commit -m 'msg'`" in result.compressed


class TestProtectedZonesInteraction:
    """Multiple protected zone types in one text."""

    def test_mixed_protected_zones(self):
        text = "check https://docs.example.com and run `make test` then look at src/main.py"
        result = compress_text(text)
        assert "https://docs.example.com" in result.compressed
        assert "`make test`" in result.compressed
        assert "src/main.py" in result.compressed

    def test_code_block_with_url_inside(self):
        text = "```bash\ncurl https://api.example.com/v1\n```"
        result = compress_text(text)
        assert "https://api.example.com/v1" in result.compressed


class TestTokenCounting:
    """Token counting for English and Chinese."""

    def test_english_word_count(self):
        result = compress_text("hello world foo bar")
        # English: count words
        assert result.original_tokens == 4

    def test_chinese_char_count(self):
        result = compress_text("请帮我检查这个代码")
        # Chinese: count chars excluding whitespace/punct
        assert result.original_tokens > 0
        assert result.language == "zh"

    def test_savings_zero_for_stub(self):
        # With all layers as stubs (no-ops), savings should be ~0%
        result = compress_text("just a simple test prompt")
        assert result.savings_pct >= 0.0
        assert result.savings_pct <= 100.0


# ===== Layer 0: Character Normalization =====


class TestLayer0CharNormalization:
    """Layer 0 normalizes Unicode characters to ASCII equivalents."""

    def test_curly_quotes_normalized(self):
        result = compress_text("\u201cHello\u201d")
        assert '"Hello"' in result.compressed

    def test_em_dash_normalized(self):
        result = compress_text("foo\u2014bar")
        assert "foo-bar" in result.compressed

    def test_en_dash_normalized(self):
        result = compress_text("foo\u2013bar")
        assert "foo-bar" in result.compressed

    def test_zero_width_chars_removed(self):
        result = compress_text("he\u200bllo")
        assert "hello" in result.compressed

    def test_zero_width_non_joiner_removed(self):
        result = compress_text("he\u200cllo")
        assert "hello" in result.compressed

    def test_zero_width_joiner_removed(self):
        result = compress_text("he\u200dllo")
        assert "hello" in result.compressed

    def test_bom_removed(self):
        result = compress_text("\ufeffhello")
        assert result.compressed.strip() == "hello"

    def test_soft_hyphen_removed(self):
        result = compress_text("hel\u00adlo")
        assert "hello" in result.compressed

    def test_nfkc_fullwidth(self):
        result = compress_text("\uff21\uff22\uff23")
        assert "ABC" in result.compressed

    def test_non_breaking_space(self):
        result = compress_text("hello\u00a0world")
        assert "hello world" in result.compressed

    def test_curly_single_quotes_normalized(self):
        result = compress_text("\u2018it\u2019s\u2019")
        assert "'" in result.compressed

    def test_multiple_normalizations_combined(self):
        result = compress_text("\u201cHello\u201d \u2014 \u200bworld")
        assert '"Hello"' in result.compressed
        assert "-" in result.compressed
        assert "world" in result.compressed

    def test_code_block_not_normalized(self):
        text = "```python\n\u201chello\u201d\n```"
        result = compress_text(text)
        assert "\u201chello\u201d" in result.compressed


# ===== Layer 2: Phrase Simplification =====


class TestLayer2PhraseSimplification:
    """Layer 2 simplifies verbose phrases to shorter equivalents."""

    def test_zh_verbose_action_simplified(self):
        result = compress_text("\u5e2e\u6211\u770b\u770b\u8fd9\u4e2a\u6587\u4ef6")
        assert "\u68c0\u67e5" in result.compressed
        assert "\u5e2e\u6211\u770b\u770b" not in result.compressed

    def test_zh_polite_prefix_removed(self):
        result = compress_text("\u80fd\u4e0d\u80fd\u5e2e\u6211\u4fee\u590d\u8fd9\u4e2abug")
        assert "\u80fd\u4e0d\u80fd\u5e2e\u6211" not in result.compressed

    def test_zh_verbose_expression(self):
        result = compress_text(
            "\u6709\u6ca1\u6709\u4ec0\u4e48\u529e\u6cd5\u89e3\u51b3\u8fd9\u4e2a\u95ee\u9898"
        )
        assert "\u5982\u4f55" in result.compressed

    def test_zh_redundant_intensifier(self):
        result = compress_text("\u8fd9\u4e2a\u975e\u5e38\u975e\u5e38\u91cd\u8981")
        assert "\u975e\u5e38\u975e\u5e38" not in result.compressed
        assert "\u975e\u5e38" in result.compressed

    def test_zh_polite_long_prefix_removed(self):
        result = compress_text(
            "\u4e0d\u597d\u610f\u601d\u6253\u6270\u4e00\u4e0b\u8bf7\u95ee\u8fd9\u4e2a\u600e\u4e48\u505a"
        )
        assert "\u4e0d\u597d\u610f\u601d\u6253\u6270\u4e00\u4e0b" not in result.compressed

    def test_en_polite_request_removed(self):
        result = compress_text("Could you please check this file")
        assert "Could you please" not in result.compressed

    def test_en_verbose_phrasing(self):
        result = compress_text("in order to fix this bug")
        assert "in order to" not in result.compressed

    def test_en_periphrastic_verb(self):
        result = compress_text("take into consideration the edge cases")
        assert "consider" in result.compressed

    def test_en_preamble_removed(self):
        result = compress_text("I'm working on a project and I need help with auth")
        assert "I'm working on a project and" not in result.compressed

    def test_en_ability_simplified(self):
        result = compress_text("this function is able to process data")
        assert "is able to" not in result.compressed
        assert "can" in result.compressed

    def test_en_wordiness_simplified(self):
        result = compress_text("due to the fact that the test failed")
        assert "due to the fact that" not in result.compressed
        assert "because" in result.compressed

    def test_longer_patterns_matched_first(self):
        result = compress_text("\u5e2e\u6211\u68c0\u67e5\u4e00\u4e0b\u8fd9\u4e2a\u9519\u8bef")
        assert "\u68c0\u67e5" in result.compressed


# ===== Layer 1: Filler Word Deletion =====


class TestLayer1FillerDeletion:
    """Layer 1 removes filler words and hedging phrases."""

    def test_zh_discourse_filler_removed(self):
        result = compress_text(
            "\u55ef\uff0c\u6211\u89c9\u5f97\u8fd9\u4e2a\u65b9\u6848\u57fa\u672c\u4e0a\u53ef\u4ee5"
        )
        assert "\u55ef" not in result.compressed
        assert "\u57fa\u672c\u4e0a" not in result.compressed

    def test_zh_tag_question_removed(self):
        result = compress_text("\u8fd9\u6837\u505a\u5bf9\u5427")
        assert "\u5bf9\u5427" not in result.compressed

    def test_zh_vague_enumerator_removed(self):
        result = compress_text("\u68c0\u67e5\u9519\u8bef\u4ec0\u4e48\u7684")
        assert "\u4ec0\u4e48\u7684" not in result.compressed

    def test_zh_temporal_filler_removed(self):
        result = compress_text("\u68c0\u67e5\u4ee3\u7801\u7684\u65f6\u5019\u6ce8\u610f\u9519\u8bef")
        assert "\u7684\u65f6\u5019" not in result.compressed

    def test_zh_hedging_phrase_removed(self):
        result = compress_text("\u5176\u5b9e\u8fd9\u4e2a\u95ee\u9898\u5f88\u7b80\u5355")
        assert "\u5176\u5b9e" not in result.compressed

    def test_en_discourse_filler_removed(self):
        result = compress_text("basically the function is broken")
        assert "basically" not in result.compressed.lower()

    def test_en_hedge_removed(self):
        result = compress_text("it seems like the test is failing")
        assert "it seems like" not in result.compressed.lower()

    def test_en_politeness_removed(self):
        result = compress_text("please check the logs thank you")
        assert "please" not in result.compressed.lower()
        assert "thank you" not in result.compressed.lower()

    def test_en_filler_well_not_partial_match(self):
        """'well' should not match inside 'dwelling' or 'well-known'."""
        result = compress_text("the dwelling is well-known")
        assert "dwelling" in result.compressed

    def test_en_hedge_i_believe(self):
        result = compress_text("I believe we should refactor this module")
        assert "I believe" not in result.compressed

    def test_en_appreciation_removed(self):
        result = compress_text("thanks in advance for your help with the API")
        assert "thanks in advance" not in result.compressed.lower()


# ===== Layer 3: Structure Cleanup =====


class TestLayer3StructureCleanup:
    """Layer 3 cleans up whitespace, markdown, and punctuation."""

    def test_excessive_newlines_collapsed(self):
        result = compress_text("line1\n\n\n\n\nline2")
        assert "\n\n\n" not in result.compressed

    def test_bold_stripped(self):
        result = compress_text("this is **important** text")
        assert "**" not in result.compressed
        assert "important" in result.compressed

    def test_italic_stripped(self):
        result = compress_text("this is *emphasized* text")
        assert result.compressed.count("*") == 0
        assert "emphasized" in result.compressed

    def test_triple_bold_italic_stripped(self):
        result = compress_text("this is ***critical*** text")
        assert "***" not in result.compressed
        assert "critical" in result.compressed

    def test_horizontal_rule_removed(self):
        result = compress_text("above\n---\nbelow")
        assert "---" not in result.compressed

    def test_long_horizontal_rule_removed(self):
        result = compress_text("above\n=======\nbelow")
        assert "=======" not in result.compressed

    def test_deep_headers_capped(self):
        result = compress_text("##### Deep Header")
        assert "#####" not in result.compressed
        assert "#### " in result.compressed

    def test_decorative_emoji_removed(self):
        result = compress_text("\U0001f600 Check this file")
        assert "\U0001f600" not in result.compressed

    def test_decorative_symbols_removed(self):
        result = compress_text("\u2713 Done \u2717 Failed")
        assert "\u2713" not in result.compressed

    def test_duplicate_chinese_punctuation(self):
        result = compress_text("\u68c0\u67e5\u4ee3\u7801\uff0c\uff0c\u4fee\u590d\u9519\u8bef")
        assert "\uff0c\uff0c" not in result.compressed

    def test_duplicate_english_commas(self):
        result = compress_text("check this,, fix that")
        assert ",," not in result.compressed

    def test_excessive_dots_collapsed(self):
        result = compress_text("wait...... for it")
        assert "......" not in result.compressed
        assert "..." in result.compressed

    def test_trailing_whitespace_on_lines(self):
        result = compress_text("line1   \nline2")
        assert "   \n" not in result.compressed

    def test_blank_lines_with_spaces(self):
        result = compress_text("line1\n   \nline2")
        # Blank line with spaces should become empty blank line
        assert "\n   \n" not in result.compressed

    def test_multiple_spaces_collapsed(self):
        result = compress_text("hello     world")
        assert "     " not in result.compressed
        assert "hello world" in result.compressed

    def test_code_block_formatting_preserved(self):
        text = "**bold** text\n```python\n**not_bold**\n```\nmore **bold**"
        result = compress_text(text)
        assert "**not_bold**" in result.compressed


# ===== Integration Tests: Full Pipeline + Edge Cases =====


class TestCompressIntegration:
    """Full pipeline integration tests combining all layers."""

    def test_full_pipeline_zh(self):
        text = (
            "嗯，帮我看看这个文件的时候，"
            "我们需要检查一下错误处理的部分，然后呢看看是否有什么问题"
        )
        result = compress_text(text)
        assert result.savings_pct > 15  # at least 15% compression
        assert len(result.changes) > 0
        assert result.language in ("zh", "mixed")

    def test_full_pipeline_en(self):
        text = (
            "Could you please take into consideration the fact that basically "
            "the function is not working in order to fix the bug"
        )
        result = compress_text(text)
        assert result.savings_pct > 15
        assert "Could you please" not in result.compressed
        assert "in order to" not in result.compressed

    def test_full_pipeline_mixed(self):
        text = "Could you please 帮我看看 this error 的时候 check the logs"
        result = compress_text(text)
        assert result.savings_pct > 0.0

    def test_token_count_zh_dominant(self):
        text = "帮我检查一下这个文件的错误处理"
        result = compress_text(text)
        assert result.original_tokens > 0
        assert result.compressed_tokens <= result.original_tokens

    def test_token_count_en_dominant(self):
        text = "Could you please check the error handling in this file"
        result = compress_text(text)
        assert result.original_tokens > 0
        assert result.compressed_tokens <= result.original_tokens

    def test_savings_pct_correct(self):
        text = "basically basically the function is broken"
        result = compress_text(text)
        if result.original_tokens > 0:
            expected = round((1 - result.compressed_tokens / result.original_tokens) * 100, 1)
            assert abs(result.savings_pct - expected) < 2.0

    def test_changes_list_format(self):
        text = "嗯，帮我看看这个文件的时候检查错误"
        result = compress_text(text)
        for change in result.changes:
            assert isinstance(change, str)

    def test_no_compression_on_clean_input(self):
        text = "Check error handling in compress.py"
        result = compress_text(text)
        assert result.savings_pct < 30

    def test_llm_output_cleanup(self):
        text = "**Step 1:** Check the code\n\n\n\n**Step 2:** Fix the bug\n---\n✓ Done"
        result = compress_text(text)
        assert "**" not in result.compressed
        assert "---" not in result.compressed
        assert "✓" not in result.compressed
        assert "\n\n\n" not in result.compressed

    def test_protected_zones_survive_full_pipeline(self):
        text = "嗯，帮我看看 `compress.py` 的时候，检查 https://example.com 的错误"
        result = compress_text(text)
        assert "`compress.py`" in result.compressed
        assert "https://example.com" in result.compressed
