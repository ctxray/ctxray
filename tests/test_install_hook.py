"""Tests for install-hook command."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


def test_install_hook_claude_code(tmp_path, monkeypatch):
    """install-hook should create a shell script in .claude/hooks/."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Create the .claude dir to simulate Claude Code installed
    (tmp_path / ".claude").mkdir()
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "installed" in result.output.lower()

    # Verify hook file was created
    hook_path = tmp_path / ".claude" / "hooks" / "reprompt-scan.sh"
    assert hook_path.exists()
    content = hook_path.read_text()
    assert "reprompt scan" in content


def test_install_hook_already_exists(tmp_path, monkeypatch):
    """install-hook should report if hook already exists."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "reprompt-scan.sh").write_text("#!/bin/sh\nreprompt scan\n")

    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "already" in result.output.lower() or "exists" in result.output.lower()


def test_install_hook_no_claude_code(tmp_path, monkeypatch):
    """install-hook should warn if Claude Code is not detected."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # No .claude dir exists
    result = runner.invoke(app, ["install-hook"])
    assert result.exit_code == 0
    assert "not detected" in result.output.lower() or "not found" in result.output.lower()


def test_install_hook_unsupported_source(tmp_path, monkeypatch):
    """install-hook for unsupported source should give a message."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = runner.invoke(app, ["install-hook", "--source", "cursor"])
    assert result.exit_code == 0
    assert "not yet supported" in result.output.lower() or "not supported" in result.output.lower()


def test_install_hook_creates_executable(tmp_path, monkeypatch):
    """Hook script should be executable."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude").mkdir()
    runner.invoke(app, ["install-hook"])

    hook_path = tmp_path / ".claude" / "hooks" / "reprompt-scan.sh"
    assert hook_path.exists()
    # Check executable bit
    import stat
    mode = hook_path.stat().st_mode
    assert mode & stat.S_IXUSR  # owner execute bit set
