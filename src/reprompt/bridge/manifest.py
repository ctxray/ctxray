"""Native Messaging host manifest generation.

Generates Chrome/Firefox/Chromium manifest JSON and detects
the correct platform-specific installation directory.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HOST_NAME = "dev.reprompt.bridge"
DESCRIPTION = "reprompt — prompt analytics bridge"
CHROME_EXTENSION_ID = "ojdccpagaanchmkninlbgbgemdcjckhn"
CHROME_STORE_URL = "https://chromewebstore.google.com/detail/reprompt/" + CHROME_EXTENSION_ID
FIREFOX_EXTENSION_ID = "reprompt@reprompt.dev"


def generate_chrome_manifest(host_path: str, extension_id: str) -> dict[str, Any]:
    """Generate Chrome/Chromium native messaging host manifest."""
    return {
        "name": HOST_NAME,
        "description": DESCRIPTION,
        "path": host_path,
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }


def generate_firefox_manifest(host_path: str) -> dict[str, Any]:
    """Generate Firefox native messaging host manifest."""
    return {
        "name": HOST_NAME,
        "description": DESCRIPTION,
        "path": host_path,
        "type": "stdio",
        "allowed_extensions": [FIREFOX_EXTENSION_ID],
    }


def get_manifest_dir(browser: str = "chrome") -> Path:
    """Return the user-level NativeMessagingHosts directory for the current platform.

    Supported browsers: chrome, chromium, firefox.
    Supported platforms: darwin (macOS), linux.
    """
    home = Path.home()
    platform = sys.platform

    if platform == "darwin":
        base = home / "Library" / "Application Support"
        if browser == "chrome":
            return base / "Google" / "Chrome" / "NativeMessagingHosts"
        if browser == "chromium":
            return base / "Chromium" / "NativeMessagingHosts"
        if browser == "firefox":
            return home / "Library" / "Application Support" / "Mozilla" / "NativeMessagingHosts"
    elif platform == "linux":
        if browser == "chrome":
            return home / ".config" / "google-chrome" / "NativeMessagingHosts"
        if browser == "chromium":
            return home / ".config" / "chromium" / "NativeMessagingHosts"
        if browser == "firefox":
            return home / ".mozilla" / "native-messaging-hosts"

    raise ValueError(f"Unsupported platform/browser: {platform}/{browser}")


def get_manifest_filename() -> str:
    """Return the manifest filename (host_name.json)."""
    return f"{HOST_NAME}.json"
