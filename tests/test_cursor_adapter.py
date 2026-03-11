"""Tests for Cursor IDE adapter."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from reprompt.adapters.cursor import CursorAdapter, _extract_prompts_from_vscdb


def _make_vscdb(tmp: Path, table: str, rows: list[tuple[str, str | bytes]]) -> Path:
    """Create a .vscdb file with the given table and rows."""
    db_path = tmp / "state.vscdb"
    conn = sqlite3.connect(str(db_path))
    if table == "cursorDiskKV":
        conn.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)")
        conn.executemany("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)", rows)
    else:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany("INSERT INTO ItemTable (key, value) VALUES (?, ?)", rows)
    conn.commit()
    conn.close()
    return db_path


class TestCursorDiskKV:
    def test_parses_composer_bubbles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ts1 = "2026-01-10T10:00:00Z"
            ts2 = "2026-01-10T10:05:00Z"
            data = {
                "conversation": [
                    {"type": 1, "text": "Add pagination to the search results", "createdAt": ts1},
                    {"type": 2, "text": "I'll add pagination using offset/limit..."},
                    {"type": 1, "text": "Now add sorting by date", "createdAt": ts2},
                ]
            }
            db_path = _make_vscdb(
                Path(tmp), "cursorDiskKV",
                [("composerData:abc-123", json.dumps(data).encode())],
            )
            prompts = _extract_prompts_from_vscdb(db_path, "test-session")
            assert len(prompts) == 2
            assert prompts[0].text == "Add pagination to the search results"
            assert prompts[1].text == "Now add sorting by date"
            assert prompts[0].source == "cursor"

    def test_skips_short_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = {"conversation": [{"type": 1, "text": "ok"}]}
            db_path = _make_vscdb(
                Path(tmp), "cursorDiskKV",
                [("composerData:x", json.dumps(data).encode())],
            )
            prompts = _extract_prompts_from_vscdb(db_path, "test")
            assert len(prompts) == 0

    def test_skips_assistant_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = {"conversation": [{"type": 2, "text": "I'll help with that."}]}
            db_path = _make_vscdb(
                Path(tmp), "cursorDiskKV",
                [("composerData:x", json.dumps(data).encode())],
            )
            prompts = _extract_prompts_from_vscdb(db_path, "test")
            assert len(prompts) == 0

    def test_handles_empty_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = _make_vscdb(Path(tmp), "cursorDiskKV", [])
            prompts = _extract_prompts_from_vscdb(db_path, "test")
            assert prompts == []

    def test_handles_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = _make_vscdb(
                Path(tmp), "cursorDiskKV",
                [("composerData:x", b"not json")],
            )
            prompts = _extract_prompts_from_vscdb(db_path, "test")
            assert prompts == []


class TestItemTable:
    def test_parses_legacy_chatdata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = [
                {
                    "messages": [
                        {"role": "user", "content": "Explain how the auth flow works"},
                        {"role": "assistant", "content": "The auth flow starts with..."},
                    ]
                }
            ]
            db_path = _make_vscdb(
                Path(tmp), "ItemTable",
                [("workbench.panel.aichat.view.aichat.chatdata", json.dumps(data))],
            )
            prompts = _extract_prompts_from_vscdb(db_path, "legacy-session")
            assert len(prompts) == 1
            assert prompts[0].text == "Explain how the auth flow works"

    def test_skips_assistant_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = [{"messages": [{"role": "assistant", "content": "Hello!"}]}]
            db_path = _make_vscdb(
                Path(tmp), "ItemTable",
                [("workbench.panel.aichat.view.aichat.chatdata", json.dumps(data))],
            )
            prompts = _extract_prompts_from_vscdb(db_path, "test")
            assert prompts == []


class TestCursorAdapter:
    def test_detect_installed_false(self) -> None:
        adapter = CursorAdapter(session_path=Path("/nonexistent/path"))
        assert adapter.detect_installed() is False

    def test_detect_installed_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CursorAdapter(session_path=Path(tmp))
            assert adapter.detect_installed() is True

    def test_adapter_name(self) -> None:
        adapter = CursorAdapter()
        assert adapter.name == "cursor"

    def test_parse_session_with_vscdb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ts = "2026-01-10T10:00:00Z"
            data = {
                "conversation": [
                    {"type": 1, "text": "Refactor the database connection pool", "createdAt": ts},
                ]
            }
            workspace_dir = Path(tmp) / "workspace-hash"
            workspace_dir.mkdir()
            db_path = _make_vscdb(
                workspace_dir, "cursorDiskKV",
                [("composerData:c1", json.dumps(data).encode())],
            )
            adapter = CursorAdapter(session_path=Path(tmp))
            prompts = adapter.parse_session(db_path)
            assert len(prompts) == 1
            assert prompts[0].source == "cursor"
            assert prompts[0].project == "workspace-hash"

    def test_nonexistent_file(self) -> None:
        adapter = CursorAdapter()
        prompts = adapter.parse_session(Path("/nonexistent/state.vscdb"))
        assert prompts == []
