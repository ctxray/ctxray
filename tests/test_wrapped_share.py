"""Tests for ctxray wrapped --share flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from ctxray.commands.wrapped import wrapped

runner = CliRunner()
app = typer.Typer()
app.command()(wrapped)


def _make_mock_report():
    from ctxray.core.persona import PERSONAS
    from ctxray.core.wrapped import WrappedReport

    return WrappedReport(
        total_prompts=100,
        scored_prompts=80,
        avg_overall=75.0,
        top_score=95.0,
        top_task_type="debug",
        avg_scores={
            "structure": 20,
            "context": 18,
            "position": 15,
            "repetition": 10,
            "clarity": 12,
        },
        persona=PERSONAS["architect"],
    )


class TestWrappedShare:
    @patch("ctxray.commands.wrapped._get_install_id", return_value="a" * 64)
    @patch("ctxray.commands.wrapped.copy_to_clipboard", return_value=True)
    @patch(
        "ctxray.commands.wrapped.upload_share", return_value="https://getreprompt.dev/w/test1234"
    )
    @patch("ctxray.core.wrapped.build_wrapped")
    @patch("ctxray.storage.db.PromptDB")
    @patch("ctxray.config.Settings")
    def test_share_prints_url(
        self,
        mock_settings,
        mock_db,
        mock_build,
        mock_upload,
        mock_clip,
        mock_id,
    ):
        mock_settings.return_value = MagicMock(
            db_path="/tmp/test.db",
            config_path="/tmp/config.toml",
        )
        mock_build.return_value = _make_mock_report()

        result = runner.invoke(app, ["--share"])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        assert "https://getreprompt.dev/w/test1234" in result.output
        mock_upload.assert_called_once()

    @patch("ctxray.commands.wrapped._get_install_id", return_value="a" * 64)
    @patch("ctxray.commands.wrapped.upload_share", side_effect=RuntimeError("auth failed"))
    @patch("ctxray.core.wrapped.build_wrapped")
    @patch("ctxray.storage.db.PromptDB")
    @patch("ctxray.config.Settings")
    def test_share_upload_error_shows_message(
        self,
        mock_settings,
        mock_db,
        mock_build,
        mock_upload,
        mock_id,
    ):
        mock_settings.return_value = MagicMock(
            db_path="/tmp/test.db",
            config_path="/tmp/config.toml",
        )
        mock_build.return_value = _make_mock_report()

        result = runner.invoke(app, ["--share"])
        assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
        assert "auth failed" in result.output or "error" in result.output.lower()
