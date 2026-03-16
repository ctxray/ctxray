"""Tests for the first-run telemetry consent prompt."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from reprompt.telemetry.consent import TelemetryConsent, read_consent
from reprompt.telemetry.prompt import maybe_prompt_consent


class TestMaybePromptConsent:
    def test_returns_false_when_already_opted_in(self, tmp_path: Path):
        from reprompt.telemetry.consent import write_consent

        config = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_IN, config)
        assert maybe_prompt_consent(config, interactive=False) is False

    def test_returns_false_when_already_opted_out(self, tmp_path: Path):
        from reprompt.telemetry.consent import write_consent

        config = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_OUT, config)
        assert maybe_prompt_consent(config, interactive=False) is False

    @patch("reprompt.telemetry.prompt._ask_consent_rich")
    def test_prompts_when_not_asked(self, mock_ask, tmp_path: Path):
        mock_ask.return_value = True
        config = tmp_path / "config.toml"
        result = maybe_prompt_consent(config, interactive=True)
        assert result is True
        assert read_consent(config) == TelemetryConsent.OPTED_IN
        mock_ask.assert_called_once()

    @patch("reprompt.telemetry.prompt._ask_consent_rich")
    def test_user_declines(self, mock_ask, tmp_path: Path):
        mock_ask.return_value = False
        config = tmp_path / "config.toml"
        result = maybe_prompt_consent(config, interactive=True)
        assert result is True  # True = prompt was shown
        assert read_consent(config) == TelemetryConsent.OPTED_OUT

    def test_non_interactive_skips_prompt(self, tmp_path: Path):
        config = tmp_path / "config.toml"
        result = maybe_prompt_consent(config, interactive=False)
        assert result is False
        assert read_consent(config) == TelemetryConsent.NOT_ASKED
