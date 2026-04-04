"""Tests for install-hook command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def test_install_hook_claude_code(tmp_path, monkeypatch):
    """install-hook should register in settings.json."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "registered" in result.output.lower()

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "hooks" in settings
    assert "Stop" in settings["hooks"]
    assert any(
        h.get("command") == "ctxray scan --source claude-code" for h in settings["hooks"]["Stop"]
    )


def test_install_hook_already_exists(tmp_path, monkeypatch):
    """install-hook should report if hook already registered."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()

    # First install
    runner.invoke(app, ["install-hook"])
    # Second install
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "already" in result.output.lower()


def test_install_hook_no_claude_code(tmp_path, monkeypatch):
    """install-hook should warn if Claude Code is not detected."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "not detected" in result.output.lower() or "not found" in result.output.lower()


def test_install_hook_unsupported_source(tmp_path, monkeypatch):
    """install-hook for unsupported source should give a message."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = runner.invoke(app, ["install-hook", "--source", "cursor"])
    assert result.exit_code == 0
    assert "not yet supported" in result.output.lower() or "not supported" in result.output.lower()


def test_install_hook_preserves_existing(tmp_path, monkeypatch):
    """install-hook should not clobber existing settings."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()
    existing = {"permissions": {"allow": ["Bash"]}, "model": "opus"}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(existing))

    runner.invoke(app, ["install-hook"])

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == ["Bash"]
    assert settings["model"] == "opus"
    assert "hooks" in settings
