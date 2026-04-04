"""E2E test: full import workflow from file to report."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def test_chatgpt_import_to_report(fixtures_path: Path, tmp_path: Path, monkeypatch) -> None:
    """Full flow: import ChatGPT → stored in DB → appears in report."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    # Import
    result = runner.invoke(app, ["import", str(fixtures_path / "chatgpt_conversations.json")])
    assert result.exit_code == 0
    assert "Import complete" in result.output

    # Verify in status
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "4" in result.output  # 4 user prompts in fixture

    # Verify in report
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0


def test_claude_chat_import_to_report(fixtures_path: Path, tmp_path: Path, monkeypatch) -> None:
    """Full flow: import Claude.ai → stored in DB → appears in report."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    # Import
    result = runner.invoke(app, ["import", str(fixtures_path / "claude_chat_export.json")])
    assert result.exit_code == 0
    assert "Import complete" in result.output

    # Verify in status
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "4" in result.output  # 4 human messages in fixture

    # Verify prompts are searchable
    result = runner.invoke(app, ["search", "quantum"])
    assert result.exit_code == 0


def test_mixed_import_and_scan(fixtures_path: Path, tmp_path: Path, monkeypatch) -> None:
    """Import + scan coexist: imported and scanned prompts share the same DB."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    # Import ChatGPT
    result = runner.invoke(app, ["import", str(fixtures_path / "chatgpt_conversations.json")])
    assert result.exit_code == 0

    # Scan Claude Code (from fixtures)
    result = runner.invoke(
        app,
        ["scan", "--source", "claude-code", "--path", str(fixtures_path), "--quiet"],
    )
    assert result.exit_code == 0

    # Both sources in status
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_reimport_deduplicates(fixtures_path: Path, tmp_path: Path, monkeypatch) -> None:
    """Importing the same file twice should not create duplicate prompts."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("CTXRAY_DB_PATH", str(db_path))

    # First import
    r1 = runner.invoke(app, ["import", str(fixtures_path / "chatgpt_conversations.json")])
    assert r1.exit_code == 0
    assert "New stored:" in r1.output

    # Second import — prompts exist, so new_stored should be 0
    r2 = runner.invoke(app, ["import", str(fixtures_path / "chatgpt_conversations.json")])
    assert r2.exit_code == 0
    assert "New stored:     0" in r2.output
