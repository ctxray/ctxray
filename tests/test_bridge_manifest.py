"""Tests for Native Messaging manifest generation."""

from __future__ import annotations

import json

from reprompt.bridge.manifest import (
    generate_chrome_manifest,
    generate_firefox_manifest,
    get_manifest_dir,
)

HOST_NAME = "dev.reprompt.bridge"


def test_chrome_manifest_structure() -> None:
    manifest = generate_chrome_manifest(
        host_path="/usr/local/bin/reprompt-bridge-host",
        extension_id="abcdefghijklmnopqrstuvwxyz123456",
    )
    assert manifest["name"] == HOST_NAME
    assert manifest["type"] == "stdio"
    assert manifest["path"] == "/usr/local/bin/reprompt-bridge-host"
    assert len(manifest["allowed_origins"]) == 1
    assert manifest["allowed_origins"][0].startswith("chrome-extension://")


def test_firefox_manifest_structure() -> None:
    manifest = generate_firefox_manifest(
        host_path="/usr/local/bin/reprompt-bridge-host",
    )
    assert manifest["name"] == HOST_NAME
    assert manifest["type"] == "stdio"
    assert "allowed_extensions" in manifest
    assert manifest["allowed_extensions"] == ["reprompt@reprompt.dev"]


def test_chrome_manifest_is_valid_json() -> None:
    manifest = generate_chrome_manifest(
        host_path="/path/to/host",
        extension_id="test123",
    )
    # Should be JSON-serializable
    text = json.dumps(manifest, indent=2)
    parsed = json.loads(text)
    assert parsed["name"] == HOST_NAME


def test_get_manifest_dir_macos(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    path = get_manifest_dir(browser="chrome")
    assert "NativeMessagingHosts" in str(path)
    assert "Google/Chrome" in str(path) or "Google" in str(path)


def test_get_manifest_dir_linux(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    path = get_manifest_dir(browser="chrome")
    assert "NativeMessagingHosts" in str(path)
    assert "google-chrome" in str(path) or "chrome" in str(path)


def test_get_manifest_dir_chromium(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    path = get_manifest_dir(browser="chromium")
    assert "Chromium" in str(path)


def test_get_manifest_dir_firefox_macos(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    path = get_manifest_dir(browser="firefox")
    assert "NativeMessagingHosts" in str(path)
    assert "Mozilla" in str(path)
