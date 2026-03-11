"""Cursor IDE session adapter.

Parses Cursor's SQLite .vscdb files to extract user prompts from
AI chat and Composer conversations.

Storage locations:
  macOS:  ~/Library/Application Support/Cursor/User/
  Linux:  ~/.config/Cursor/User/
"""

from __future__ import annotations

import json
import platform
import sqlite3
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt
from reprompt.core.models import Prompt


def _default_cursor_path() -> str:
    """Return default Cursor storage path for current OS."""
    if platform.system() == "Darwin":
        return "~/Library/Application Support/Cursor/User"
    return "~/.config/Cursor/User"


def _extract_prompts_from_vscdb(db_path: Path, session_id: str) -> list[Prompt]:
    """Extract user prompts from a Cursor .vscdb file."""
    prompts: list[Prompt] = []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return prompts

    try:
        # Try current schema: cursorDiskKV table (Cursor 2.0+)
        prompts = _parse_cursor_disk_kv(conn, session_id)

        # Fallback to legacy schema: ItemTable
        if not prompts:
            prompts = _parse_item_table(conn, session_id)
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

    return prompts


def _parse_cursor_disk_kv(conn: sqlite3.Connection, session_id: str) -> list[Prompt]:
    """Parse cursorDiskKV table (Cursor 2.0+ Composer format)."""
    prompts: list[Prompt] = []

    try:
        rows = conn.execute(
            "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
        ).fetchall()
    except sqlite3.OperationalError:
        return prompts

    for key, value in rows:
        try:
            if isinstance(value, bytes):
                data = json.loads(value.decode("utf-8", errors="replace"))
            else:
                data = json.loads(value)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        # composerData contains conversation metadata
        if not isinstance(data, dict):
            continue

        composer_id = key.split(":", 1)[-1] if ":" in key else session_id

        # Extract from conversation/bubbles structure
        for bubble in data.get("conversation") or data.get("bubbles") or []:
            if not isinstance(bubble, dict):
                continue

            # type 1 = user message
            if bubble.get("type") != 1:
                continue

            text = bubble.get("text", "").strip()
            if not should_keep_prompt(text):
                continue

            timestamp = bubble.get("createdAt", "")

            prompts.append(
                Prompt(
                    text=text,
                    source="cursor",
                    session_id=composer_id,
                    project=session_id,
                    timestamp=timestamp,
                )
            )

    return prompts


def _parse_item_table(conn: sqlite3.Connection, session_id: str) -> list[Prompt]:
    """Parse legacy ItemTable format."""
    prompts: list[Prompt] = []

    try:
        rows = conn.execute(
            "SELECT key, value FROM ItemTable WHERE key LIKE '%chatdata%' OR key LIKE '%prompts%'"
        ).fetchall()
    except sqlite3.OperationalError:
        return prompts

    for key, value in rows:
        try:
            data = (
                json.loads(value)
                if isinstance(value, str)
                else json.loads(value.decode("utf-8", errors="replace"))
            )
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            continue

        # chatdata contains a list of conversations
        conversations = data if isinstance(data, list) else [data]
        for convo in conversations:
            if not isinstance(convo, dict):
                continue
            for msg in convo.get("messages") or convo.get("bubbles") or []:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", msg.get("type", ""))
                if role not in ("user", 1):
                    continue
                text = str(msg.get("content") or msg.get("text") or "").strip()
                if not should_keep_prompt(text):
                    continue

                prompts.append(
                    Prompt(
                        text=text,
                        source="cursor",
                        session_id=session_id,
                        timestamp=msg.get("createdAt", ""),
                    )
                )

    return prompts


class CursorAdapter(BaseAdapter):
    """Adapter for Cursor IDE chat history."""

    name = "cursor"
    default_session_path = _default_cursor_path()

    def __init__(self, session_path: Path | None = None) -> None:
        self._session_path = session_path or Path(self.default_session_path).expanduser()

    def detect_installed(self) -> bool:
        """Check if Cursor data directory exists."""
        return self._session_path.is_dir()

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a Cursor .vscdb file into Prompt objects."""
        session_id = path.parent.name if path.name == "state.vscdb" else path.stem
        return _extract_prompts_from_vscdb(path, session_id)
