"""Cline (VS Code AI agent) session adapter.

Parses ``api_conversation_history.json`` files stored under
``globalStorage/saoudrizwan.claude-dev/tasks/<task-id>/``.
Each file is a JSON array of Anthropic ``MessageParam`` objects with
``role`` (``"user"``/``"assistant"``) and ``content`` (string or list of blocks).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.claude_code import should_keep_prompt
from reprompt.core.models import Prompt

_EXTENSION_ID = "saoudrizwan.claude-dev"


def _default_storage_paths() -> list[Path]:
    """Return platform-specific globalStorage paths for Cline."""
    paths: list[Path] = []
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
        for editor in ("Code", "Cursor", "Cursor Nightly", "VSCodium"):
            paths.append(base / editor / "User" / "globalStorage" / _EXTENSION_ID)
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            for editor in ("Code", "Cursor"):
                paths.append(Path(appdata) / editor / "User" / "globalStorage" / _EXTENSION_ID)
    else:  # Linux
        config = Path.home() / ".config"
        for editor in ("Code", "Cursor", "VSCodium"):
            paths.append(config / editor / "User" / "globalStorage" / _EXTENSION_ID)
    return paths


class ClineAdapter(BaseAdapter):
    """Adapter for Cline (VS Code AI agent) task history files."""

    name = "cline"
    default_session_path = f"~/Library/Application Support/Code/User/globalStorage/{_EXTENSION_ID}"

    def __init__(self, storage_paths: list[Path] | None = None) -> None:
        self._storage_paths = storage_paths or _default_storage_paths()

    def detect_installed(self) -> bool:
        """Check if any Cline task directories exist."""
        return len(self.discover_sessions()) > 0

    def discover_sessions(self) -> list[Path]:
        """Find all api_conversation_history.json files across storage paths."""
        found: list[Path] = []
        seen: set[str] = set()
        for root in self._storage_paths:
            tasks_dir = root / "tasks"
            if not tasks_dir.is_dir():
                continue
            for f in sorted(tasks_dir.rglob("api_conversation_history.json")):
                real = str(f.resolve())
                if real not in seen:
                    seen.add(real)
                    found.append(f)
        return found

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a Cline api_conversation_history.json into Prompt objects."""
        try:
            messages = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []

        if not isinstance(messages, list):
            return []

        task_id = self._project_from_path(str(path))
        prompts: list[Prompt] = []

        for msg in messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")
            text = self._extract_text(content)
            if not text or not should_keep_prompt(text):
                continue

            prompts.append(
                Prompt(
                    text=text,
                    source=self.name,
                    session_id=task_id,
                    project=task_id,
                    timestamp="",
                )
            )

        return prompts

    @staticmethod
    def _extract_text(content: str | list) -> str:
        """Extract user text from content, skipping tool_result blocks."""
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            # Check if this is a tool_result message
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                return ""
            # Extract text blocks only
            parts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            return " ".join(parts).strip()

        return ""

    @staticmethod
    def _project_from_path(path: str) -> str:
        """Extract task ID from path (parent directory name)."""
        return Path(path).parent.name
