"""Tests for bridge CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


def test_install_extension_chrome(tmp_path, monkeypatch) -> None:
    """install-extension creates manifest file for Chrome."""
    # Patch manifest dir to tmp
    import reprompt.bridge.manifest as manifest_mod

    monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: tmp_path)
    monkeypatch.setattr("reprompt.cli._create_host_wrapper", lambda: tmp_path / "host.sh")

    result = runner.invoke(
        app,
        ["install-extension", "--browser", "chrome", "--extension-id", "testid123"],
    )
    assert result.exit_code == 0
    assert "registered" in result.output.lower()
    # Manifest file should exist
    manifest_file = tmp_path / "dev.reprompt.bridge.json"
    assert manifest_file.exists()


def test_install_extension_no_id_warns(tmp_path, monkeypatch) -> None:
    """install-extension without --extension-id shows warning."""
    import reprompt.bridge.manifest as manifest_mod

    monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: tmp_path)
    monkeypatch.setattr("reprompt.cli._create_host_wrapper", lambda: tmp_path / "host.sh")

    result = runner.invoke(app, ["install-extension", "--browser", "chrome"])
    assert result.exit_code == 0
    assert "placeholder" in result.output.lower() or "no --extension-id" in result.output.lower()


def test_extension_status_not_registered(tmp_path, monkeypatch) -> None:
    """extension-status shows 'not registered' when no manifest exists."""
    import reprompt.bridge.manifest as manifest_mod

    monkeypatch.setattr(manifest_mod, "get_manifest_dir", lambda browser: tmp_path / "nonexistent")
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))

    result = runner.invoke(app, ["extension-status"])
    assert result.exit_code == 0
    assert "not registered" in result.output.lower()
