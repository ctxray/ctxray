"""Claude.ai chat export adapter.

Parses Claude.ai data exports (Settings -> Privacy -> Export Data).
Export arrives as a ZIP containing ``conversations.json`` (array of conversations)
or as a standalone JSON file (single or array).

Each conversation has ``chat_messages`` -- a flat array of messages with
``sender`` ("human"/"assistant") and ``content`` (array of typed items).
User messages: ``sender == "human"``.
Content: extract ``text`` from items where ``type == "text"``.

Different from ``claude_code.py`` which parses Claude Code CLI JSONL sessions.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt
from reprompt.core.models import Prompt


class ClaudeChatAdapter(BaseAdapter):
    """Adapter for Claude.ai web chat export files."""

    name = "claude-chat-export"
    default_session_path = "~"  # Not auto-discovered; used via `reprompt import`

    def detect_installed(self) -> bool:
        """Claude.ai exports are explicit files -- never auto-detected."""
        return False

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a Claude.ai export (JSON or ZIP) into Prompt objects."""
        path = Path(path)
        data = _load_export(path)
        if data is None:
            return []

        # Normalize: single conversation dict -> list
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        prompts: list[Prompt] = []
        for conversation in data:
            name = conversation.get("name", "untitled")
            conv_uuid = conversation.get("uuid", "unknown")
            messages = conversation.get("chat_messages", [])

            for msg in messages:
                if msg.get("sender") != "human":
                    continue
                text = _extract_text(msg)
                if not should_keep_prompt(text):
                    continue
                prompts.append(
                    Prompt(
                        text=text,
                        source=self.name,
                        session_id=conv_uuid,
                        project=name,
                        timestamp=_format_timestamp(msg.get("created_at", "")),
                    )
                )

        return prompts


def _load_export(path: Path) -> list | dict | None:
    """Load JSON from a file or from conversations.json inside a ZIP."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".zip" or suffix == ".dms":
            with zipfile.ZipFile(path) as zf:
                # Look for conversations.json inside the ZIP
                candidates = [n for n in zf.namelist() if n.endswith("conversations.json")]
                if not candidates:
                    # Fallback: first .json file
                    candidates = [n for n in zf.namelist() if n.endswith(".json")]
                if not candidates:
                    return None
                raw = zf.read(candidates[0])
                return json.loads(raw)
        else:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError):
        return None


def _extract_text(message: dict) -> str:
    """Extract text from message content items."""
    # Prefer structured content array
    content = message.get("content", [])
    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        joined = " ".join(text_parts).strip()
        if joined:
            return joined
    # Fallback to flat text field
    return str(message.get("text", "")).strip()


def _format_timestamp(ts: str) -> str:
    """Normalize ISO timestamp to 'YYYY-MM-DD HH:MM:SS'."""
    if not ts:
        return ""
    # Handle various ISO formats
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            from datetime import datetime, timezone

            dt = datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return ts
