"""Tests for cross-platform clipboard helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from reprompt.sharing.clipboard import copy_to_clipboard


class TestCopyToClipboard:
    @patch("subprocess.run")
    def test_macos_uses_pbcopy(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with patch("reprompt.sharing.clipboard.sys") as mock_sys:
            mock_sys.platform = "darwin"
            result = copy_to_clipboard("https://getreprompt.dev/w/abc")
        assert result is True
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["pbcopy"]

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_returns_false_on_missing_tool(self, mock_run):
        result = copy_to_clipboard("test")
        assert result is False
