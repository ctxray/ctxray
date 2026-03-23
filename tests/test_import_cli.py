"""Tests for reprompt import CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from reprompt.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a temp DB so import tests don't pollute the user's real database."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))


def test_import_chatgpt(fixtures_path: Path) -> None:
    result = runner.invoke(app, ["import", str(fixtures_path / "chatgpt_conversations.json")])
    assert result.exit_code == 0
    assert "Import complete" in result.output
    assert "chatgpt-export" in result.output


def test_import_claude_chat(fixtures_path: Path) -> None:
    result = runner.invoke(app, ["import", str(fixtures_path / "claude_chat_export.json")])
    assert result.exit_code == 0
    assert "Import complete" in result.output
    assert "claude-chat-export" in result.output


def test_import_with_explicit_source(fixtures_path: Path) -> None:
    result = runner.invoke(
        app,
        ["import", str(fixtures_path / "chatgpt_conversations.json"), "--source", "chatgpt"],
    )
    assert result.exit_code == 0
    assert "chatgpt-export" in result.output


def test_import_nonexistent_file() -> None:
    result = runner.invoke(app, ["import", "/tmp/nonexistent_file_12345.json"])
    assert (
        result.exit_code != 0
        or "not found" in result.output.lower()
        or "error" in result.output.lower()
    )


def test_import_auto_detect_chatgpt(tmp_path: Path) -> None:
    """Auto-detect ChatGPT format from mapping structure."""
    data = [
        {
            "title": "test",
            "create_time": 1.0,
            "update_time": 1.0,
            "mapping": {
                "root": {"id": "root", "parent": None, "children": ["u1"], "message": None},
                "u1": {
                    "id": "u1",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "u1",
                        "author": {"role": "user"},
                        "create_time": 1.0,
                        "content": {
                            "content_type": "text",
                            "parts": ["Auto-detected ChatGPT prompt test"],
                        },
                    },
                },
            },
        }
    ]
    f = tmp_path / "export.json"
    f.write_text(json.dumps(data))
    result = runner.invoke(app, ["import", str(f)])
    assert result.exit_code == 0
    assert "chatgpt-export" in result.output


def test_import_zip_autodetects_claude(tmp_path: Path) -> None:
    """ZIP files auto-detect as Claude.ai export."""
    import zipfile

    conversations = [
        {
            "uuid": "z1",
            "name": "zip test",
            "created_at": "2026-03-01T10:00:00Z",
            "updated_at": "2026-03-01T10:00:00Z",
            "chat_messages": [
                {
                    "uuid": "m1",
                    "sender": "human",
                    "content": [
                        {
                            "type": "text",
                            "text": "Zip autodetect test prompt for CLI validation",
                        }
                    ],
                    "created_at": "2026-03-01T10:00:00Z",
                    "updated_at": "2026-03-01T10:00:00Z",
                    "index": 0,
                    "truncated": False,
                }
            ],
        }
    ]
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("conversations.json", json.dumps(conversations))
    result = runner.invoke(app, ["import", str(zip_path)])
    assert result.exit_code == 0
    assert "claude-chat-export" in result.output


def test_import_auto_detect_claude(tmp_path: Path) -> None:
    """Auto-detect Claude format from chat_messages + sender structure."""
    data = [
        {
            "uuid": "c1",
            "name": "test",
            "created_at": "2026-03-01T10:00:00Z",
            "updated_at": "2026-03-01T10:00:00Z",
            "chat_messages": [
                {
                    "uuid": "m1",
                    "sender": "human",
                    "content": [{"type": "text", "text": "Auto-detected Claude chat prompt test"}],
                    "created_at": "2026-03-01T10:00:00Z",
                    "updated_at": "2026-03-01T10:00:00Z",
                    "index": 0,
                    "truncated": False,
                }
            ],
        }
    ]
    f = tmp_path / "export.json"
    f.write_text(json.dumps(data))
    result = runner.invoke(app, ["import", str(f)])
    assert result.exit_code == 0
    assert "claude-chat-export" in result.output
