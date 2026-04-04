"""Telemetry consent management and install ID generation.

Privacy guarantees:
- install_id is sha256(machine_uuid + random_salt), not reversible
- Consent stored in user's TOML config, never transmitted
- Default is NOT_ASKED -- telemetry never fires without explicit opt-in
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from enum import Enum
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redefine]


class TelemetryConsent(Enum):
    """User's telemetry consent state."""

    NOT_ASKED = "not_asked"
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"


def generate_install_id(salt: str) -> str:
    """Generate a one-way install ID from machine UUID + salt.

    Returns a SHA-256 hex digest (64 chars). Not reversible to machine identity.
    """
    machine_id = str(uuid.getnode())  # MAC-based integer
    return hashlib.sha256(f"{machine_id}:{salt}".encode()).hexdigest()


def get_or_create_salt(config_path: Path) -> str:
    """Read telemetry_salt from TOML config, or generate and persist one.

    The salt is a random UUID4 hex string (32 chars, no dashes).
    Once created it never changes -- this keeps install_id stable.
    """
    # Try to read existing salt
    if config_path.is_file():
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            existing = data.get("ctxray", {}).get("telemetry_salt")
            if existing:
                return str(existing)
        except Exception:
            pass

    # Generate new salt and persist
    salt = uuid.uuid4().hex  # 32 hex chars, no dashes
    _upsert_toml_key(config_path, "telemetry_salt", salt)
    return salt


def read_consent(config_path: Path) -> TelemetryConsent:
    """Read telemetry consent from TOML config. Returns NOT_ASKED if missing."""
    if not config_path.is_file():
        return TelemetryConsent.NOT_ASKED
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        raw = data.get("ctxray", {}).get("telemetry_consent", "not_asked")
        return TelemetryConsent(raw)
    except Exception:
        return TelemetryConsent.NOT_ASKED


def write_consent(consent: TelemetryConsent, config_path: Path) -> None:
    """Write telemetry consent to TOML config, preserving other settings."""
    _upsert_toml_key(config_path, "telemetry_consent", consent.value)


def _upsert_toml_key(config_path: Path, key: str, value: str) -> None:
    """Insert or update a key under [ctxray] in the TOML config file.

    Preserves all other content. Creates the file + parent dirs if needed.
    Uses simple string manipulation (no TOML writer dependency).
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.is_file():
        content = config_path.read_text()
    else:
        content = ""

    # Ensure [ctxray] section exists
    if "[ctxray]" not in content:
        if content and not content.endswith("\n"):
            content += "\n"
        content += "[ctxray]\n"

    # Check if key already exists under [ctxray]
    lines = content.split("\n")
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}") and "=" in stripped:
            # Verify it's actually this key (not a prefix match)
            left = stripped.split("=", 1)[0].strip()
            if left == key:
                lines[i] = f'{key} = "{value}"'
                found = True
                break

    if not found:
        # Insert after [ctxray] line
        for i, line in enumerate(lines):
            if line.strip() == "[ctxray]":
                lines.insert(i + 1, f'{key} = "{value}"')
                break

    config_path.write_text("\n".join(lines))
