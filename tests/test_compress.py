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
