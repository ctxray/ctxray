"""Tests for telemetry consent and install ID."""

from __future__ import annotations

from pathlib import Path

from ctxray.telemetry.consent import (
    TelemetryConsent,
    generate_install_id,
    get_or_create_salt,
    read_consent,
    write_consent,
)


class TestTelemetryConsent:
    def test_consent_enum_values(self):
        assert TelemetryConsent.NOT_ASKED.value == "not_asked"
        assert TelemetryConsent.OPTED_IN.value == "opted_in"
        assert TelemetryConsent.OPTED_OUT.value == "opted_out"

    def test_consent_default_is_not_asked(self):
        assert TelemetryConsent.NOT_ASKED == TelemetryConsent("not_asked")


class TestInstallId:
    def test_generate_install_id_returns_hex_string(self):
        salt = "test-salt-value"
        install_id = generate_install_id(salt)
        assert isinstance(install_id, str)
        assert len(install_id) == 64  # sha256 hex digest

    def test_generate_install_id_is_deterministic(self):
        salt = "fixed-salt"
        id1 = generate_install_id(salt)
        id2 = generate_install_id(salt)
        assert id1 == id2

    def test_generate_install_id_differs_with_salt(self):
        id1 = generate_install_id("salt-a")
        id2 = generate_install_id("salt-b")
        assert id1 != id2

    def test_generate_install_id_uses_sha256(self):
        salt = "verify-hash"
        install_id = generate_install_id(salt)
        # Just verify it's valid hex
        int(install_id, 16)


class TestSalt:
    def test_get_or_create_salt_creates_new(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        salt = get_or_create_salt(config_path)
        assert isinstance(salt, str)
        assert len(salt) == 32  # uuid4 hex (no dashes)

    def test_get_or_create_salt_is_stable(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        salt1 = get_or_create_salt(config_path)
        salt2 = get_or_create_salt(config_path)
        assert salt1 == salt2

    def test_get_or_create_salt_reads_from_existing_toml(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text('[ctxray]\ntelemetry_salt = "my-fixed-salt"\n')
        salt = get_or_create_salt(config_path)
        assert salt == "my-fixed-salt"


class TestConsentPersistence:
    def test_write_and_read_consent(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_IN, config_path)
        assert read_consent(config_path) == TelemetryConsent.OPTED_IN

    def test_read_consent_default_not_asked(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        assert read_consent(config_path) == TelemetryConsent.NOT_ASKED

    def test_write_consent_preserves_other_settings(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text('[ctxray]\nembedding_backend = "ollama"\n')
        write_consent(TelemetryConsent.OPTED_OUT, config_path)
        text = config_path.read_text()
        assert "ollama" in text
        assert "opted_out" in text

    def test_write_consent_creates_file_if_missing(self, tmp_path: Path):
        config_path = tmp_path / "subdir" / "config.toml"
        write_consent(TelemetryConsent.OPTED_IN, config_path)
        assert config_path.exists()
        assert read_consent(config_path) == TelemetryConsent.OPTED_IN

    def test_opt_out_then_opt_in(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_OUT, config_path)
        assert read_consent(config_path) == TelemetryConsent.OPTED_OUT
        write_consent(TelemetryConsent.OPTED_IN, config_path)
        assert read_consent(config_path) == TelemetryConsent.OPTED_IN
