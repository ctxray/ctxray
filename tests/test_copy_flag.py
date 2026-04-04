# tests/test_copy_flag.py
"""Tests for --copy flag standardization across CLI commands."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


class TestScoreCopy:
    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=True)
    def test_score_copy(self, mock_clip):
        result = runner.invoke(app, ["score", "--copy", "Fix the bug in auth.py"])
        assert result.exit_code == 0
        mock_clip.assert_called_once()
        assert "Copied to clipboard" in result.output

    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=True)
    def test_score_copy_json_quiet(self, mock_clip):
        result = runner.invoke(app, ["score", "--json", "--copy", "Fix the bug"])
        assert result.exit_code == 0
        mock_clip.assert_called_once()
        # Should NOT show "Copied" message in json mode
        assert "Copied to clipboard" not in result.output

    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=False)
    def test_score_copy_failure(self, mock_clip):
        result = runner.invoke(app, ["score", "--copy", "Fix the bug"])
        assert result.exit_code == 0
        assert "Could not copy" in result.output


class TestCompareCopy:
    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=True)
    def test_compare_copy(self, mock_clip):
        result = runner.invoke(
            app, ["compare", "--copy", "Fix the bug", "Fix TypeError in auth.py:42"]
        )
        assert result.exit_code == 0
        mock_clip.assert_called_once()
        # Verify JSON data was copied
        import json

        copied_text = mock_clip.call_args[0][0]
        data = json.loads(copied_text)
        assert "prompt_a" in data
        assert "prompt_b" in data


class TestSearchCopy:
    def test_search_copy_no_results(self):
        """--copy with no results should not crash."""
        result = runner.invoke(app, ["search", "--copy", "xyznonexistent99999"])
        assert result.exit_code == 0


class TestLintCopy:
    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=True)
    def test_lint_copy(self, mock_clip):
        # Lint exits 1 on violations, 0 on clean — both are valid
        result = runner.invoke(app, ["lint", "--copy"])
        assert result.exit_code in (0, 1)
        # If prompts were found, clipboard was used
        if "No prompts found" not in result.output:
            mock_clip.assert_called_once()


class TestCompressCopy:
    """Verify existing compress --copy still works after refactor."""

    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=True)
    def test_compress_copy(self, mock_clip):
        result = runner.invoke(app, ["compress", "--copy", "Please help me fix the bug"])
        assert result.exit_code == 0
        mock_clip.assert_called_once()
        assert "Copied to clipboard" in result.output

    @patch("ctxray.sharing.clipboard.copy_to_clipboard", return_value=True)
    def test_compress_copy_json_quiet(self, mock_clip):
        result = runner.invoke(app, ["compress", "--json", "--copy", "Please help me fix the bug"])
        assert result.exit_code == 0
        mock_clip.assert_called_once()
        assert "Copied to clipboard" not in result.output


class TestCopyFlagExists:
    """Verify --copy is accepted (not rejected) by all target commands."""

    def test_score_accepts_copy(self):
        result = runner.invoke(app, ["score", "--copy", "test"])
        assert result.exit_code == 0

    def test_compare_accepts_copy(self):
        result = runner.invoke(app, ["compare", "--copy", "a", "b"])
        assert result.exit_code == 0

    def test_search_accepts_copy(self):
        result = runner.invoke(app, ["search", "--copy", "test"])
        assert result.exit_code == 0

    def test_lint_accepts_copy(self):
        result = runner.invoke(app, ["lint", "--copy"])
        # exit 0 = clean, exit 1 = violations found — both valid
        assert result.exit_code in (0, 1)

    def test_style_accepts_copy(self):
        result = runner.invoke(app, ["style", "--copy"])
        assert result.exit_code == 0

    def test_insights_accepts_copy(self):
        result = runner.invoke(app, ["insights", "--copy"])
        assert result.exit_code == 0

    def test_privacy_accepts_copy(self):
        result = runner.invoke(app, ["privacy", "--copy"])
        assert result.exit_code == 0

    def test_digest_accepts_copy(self):
        result = runner.invoke(app, ["digest", "--copy"])
        assert result.exit_code == 0

    def test_compress_accepts_copy(self):
        result = runner.invoke(app, ["compress", "--copy", "test"])
        assert result.exit_code == 0

    def test_distill_accepts_copy(self):
        result = runner.invoke(app, ["distill", "--copy"])
        assert result.exit_code == 0
