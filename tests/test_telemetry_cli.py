"""Tests for reprompt telemetry CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.telemetry.consent import TelemetryConsent, read_consent, write_consent

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect config path and DB path to tmp for all tests."""
    config_path = tmp_path / "config.toml"
    db_path = tmp_path / "reprompt.db"
    monkeypatch.setenv("REPROMPT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))
    return config_path


class TestTelemetryOn:
    def test_telemetry_on(self, isolated_config: Path):
        result = runner.invoke(app, ["telemetry", "on"])
        assert result.exit_code == 0
        assert "enabled" in result.output.lower() or "opted in" in result.output.lower()
        assert read_consent(isolated_config) == TelemetryConsent.OPTED_IN

    def test_telemetry_on_idempotent(self, isolated_config: Path):
        runner.invoke(app, ["telemetry", "on"])
        result = runner.invoke(app, ["telemetry", "on"])
        assert result.exit_code == 0
        assert read_consent(isolated_config) == TelemetryConsent.OPTED_IN


class TestTelemetryOff:
    def test_telemetry_off(self, isolated_config: Path):
        write_consent(TelemetryConsent.OPTED_IN, isolated_config)
        result = runner.invoke(app, ["telemetry", "off"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower() or "opted out" in result.output.lower()
        assert read_consent(isolated_config) == TelemetryConsent.OPTED_OUT


class TestTelemetryStatus:
    def test_status_not_asked(self, isolated_config: Path):
        result = runner.invoke(app, ["telemetry", "status"])
        assert result.exit_code == 0
        assert "not" in result.output.lower()

    def test_status_opted_in(self, isolated_config: Path):
        write_consent(TelemetryConsent.OPTED_IN, isolated_config)
        result = runner.invoke(app, ["telemetry", "status"])
        assert result.exit_code == 0
        # Should show status and privacy info
        assert "enabled" in result.output.lower() or "opted in" in result.output.lower()

    def test_status_opted_out(self, isolated_config: Path):
        write_consent(TelemetryConsent.OPTED_OUT, isolated_config)
        result = runner.invoke(app, ["telemetry", "status"])
        assert result.exit_code == 0
        assert "disabled" in result.output.lower() or "opted out" in result.output.lower()

    def test_status_shows_privacy_info(self, isolated_config: Path):
        write_consent(TelemetryConsent.OPTED_IN, isolated_config)
        result = runner.invoke(app, ["telemetry", "status"])
        # Should mention what IS and ISN'T collected
        output = result.output.lower()
        assert "dna" in output or "feature" in output
        assert "no prompt text" in output or "never" in output


class TestScoreTelemetryIntegration:
    @patch("reprompt.telemetry.collector.send_batch")
    def test_score_records_telemetry_when_opted_in(self, mock_send, isolated_config: Path):
        mock_send.return_value = True
        write_consent(TelemetryConsent.OPTED_IN, isolated_config)
        result = runner.invoke(app, ["score", "Fix the auth bug in login.ts"])
        assert result.exit_code == 0

    def test_score_works_without_telemetry(self, isolated_config: Path):
        """score should work fine even when telemetry is NOT_ASKED."""
        result = runner.invoke(app, ["score", "Fix the auth bug in login.ts"])
        assert result.exit_code == 0
