"""Tests for bridge CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def test_install_extension_chrome(tmp_path, monkeypatch) -> None:
    """install-extension creates manifest file for Chrome."""
    # Patch manifest dir to tmp
    import ctxray.bridge.manifest as manifest_mod

    monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: tmp_path)
    monkeypatch.setattr("ctxray.cli._create_host_wrapper", lambda: tmp_path / "host.sh")

    result = runner.invoke(
        app,
        ["install-extension", "--browser", "chrome", "--extension-id", "testid123"],
    )
    assert result.exit_code == 0
    assert "registered" in result.output.lower()
    # Manifest file should exist
    manifest_file = tmp_path / "dev.ctxray.bridge.json"
    assert manifest_file.exists()


def test_install_extension_default_id(tmp_path, monkeypatch) -> None:
    """install-extension without --extension-id uses published Chrome Web Store ID."""
    import json

    import ctxray.bridge.manifest as manifest_mod

    monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: tmp_path)
    monkeypatch.setattr("ctxray.cli._create_host_wrapper", lambda: tmp_path / "host.sh")

    result = runner.invoke(app, ["install-extension", "--browser", "chrome"])
    assert result.exit_code == 0
    assert "registered" in result.output.lower()
    assert "chromewebstore.google.com" in result.output

    # Verify manifest uses the published extension ID
    manifest_file = tmp_path / "dev.ctxray.bridge.json"
    manifest = json.loads(manifest_file.read_text())
    assert manifest_mod.CHROME_EXTENSION_ID in manifest["allowed_origins"][0]


def test_extension_status_not_registered(tmp_path, monkeypatch) -> None:
    """extension-status shows 'not registered' with Chrome Web Store link."""
    import ctxray.bridge.manifest as manifest_mod

    monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: tmp_path / "nonexistent")
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    result = runner.invoke(app, ["extension-status"])
    assert result.exit_code == 0
    assert "not registered" in result.output.lower()
    assert "chromewebstore.google.com" in result.output
