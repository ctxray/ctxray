"""Gemini CLI session adapter.

Parses ``session-*.json`` files stored under ``~/.gemini/tmp/<hash>/chats/``.
Each file is a JSON object with a ``messages`` array where entries have a
``type`` field: ``"user"`` for human prompts, ``"gemini"`` for AI responses,
and ``"info"``/``"error"``/``"warning"`` for system messages.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt
from reprompt.core.models import Prompt

_DEFAULT_GEMINI_HOME = "~/.gemini"


class GeminiAdapter(BaseAdapter):
    """Adapter for Google Gemini CLI session files."""

    name = "gemini"
    default_session_path = _DEFAULT_GEMINI_HOME

    def __init__(self, gemini_home: Path | None = None) -> None:
        self._home = gemini_home or Path(os.path.expanduser(_DEFAULT_GEMINI_HOME))

    def detect_installed(self) -> bool:
        """Check if any Gemini CLI session files exist."""
        return len(self.discover_sessions()) > 0

    def discover_sessions(self) -> list[Path]:
        """Find all session-*.json files under ~/.gemini/tmp/*/chats/."""
        tmp = self._home / "tmp"
        if not tmp.is_dir():
            return []
        return sorted(tmp.rglob("session-*.json"))

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a Gemini CLI session JSON file into Prompt objects."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []

        session_id = data.get("sessionId", path.stem)
        prompts: list[Prompt] = []

        for msg in data.get("messages", []):
            if msg.get("type") != "user":
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict) and "text" in p
                )
            text = str(content).strip()

            if not should_keep_prompt(text):
                continue

            prompts.append(
                Prompt(
                    text=text,
                    source=self.name,
                    session_id=session_id,
                    project=data.get("projectHash", ""),
                    timestamp=msg.get("timestamp", ""),
                )
            )

        return prompts
