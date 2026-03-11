"""OpenClaw/OpenCode session adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt
from reprompt.core.models import Prompt

# New path (post-rebrand): ~/.openclaw/agents/<agentId>/sessions/
_NEW_DEFAULT_PATH = "~/.openclaw"
# Legacy path (OpenCode): ~/.opencode/sessions/
_LEGACY_DEFAULT_PATH = "~/.opencode/sessions"


class OpenClawAdapter(BaseAdapter):
    """Adapter for OpenClaw/OpenCode JSONL session files.

    OpenClaw sessions use a simpler format than Claude Code:
    - No 'type' wrapper -- directly has 'role' field
    - 'content' is always a string (not list)

    Supports both path layouts:
    - New (post-rebrand):  ~/.openclaw/agents/<agentId>/sessions/
    - Legacy (OpenCode):   ~/.opencode/sessions/
    """

    name = "openclaw"
    default_session_path = _NEW_DEFAULT_PATH

    def __init__(
        self,
        session_path: Path | None = None,
        legacy_path: Path | None = None,
    ) -> None:
        # Primary path — new ~/.openclaw layout (or caller-supplied override)
        self._session_path = session_path or Path(os.path.expanduser(_NEW_DEFAULT_PATH))
        # Legacy fallback — old ~/.opencode/sessions layout
        self._legacy_path = legacy_path or Path(os.path.expanduser(_LEGACY_DEFAULT_PATH))

    def detect_installed(self) -> bool:
        """Check if OpenClaw/OpenCode session directory exists (either location)."""
        return self._session_path.is_dir() or self._legacy_path.is_dir()

    def discover_sessions(self) -> list[Path]:
        """Return all JSONL session files from both new and legacy paths.

        Search order:
        1. New path: ~/.openclaw/agents/<agentId>/sessions/**/*.jsonl
        2. Legacy path: ~/.opencode/sessions/**/*.jsonl
        """
        found: list[Path] = []
        for root in (self._session_path, self._legacy_path):
            if root.is_dir():
                found.extend(sorted(root.rglob("*.jsonl")))
        return found

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse an OpenClaw JSONL session file into Prompt objects."""
        prompts: list[Prompt] = []

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only process user messages
                if entry.get("role") != "user":
                    continue

                text = str(entry.get("content", "")).strip()
                if not should_keep_prompt(text):
                    continue

                session_id = entry.get("session_id", path.stem)
                timestamp = entry.get("timestamp", "")
                project = self._project_from_path(str(path))

                prompts.append(
                    Prompt(
                        text=text,
                        source=self.name,
                        session_id=session_id,
                        project=project,
                        timestamp=timestamp,
                    )
                )

        return prompts

    def _project_from_path(self, file_path: str) -> str:
        """Extract project name from an OpenClaw/OpenCode session path.

        New path format:  ~/.openclaw/agents/<agentId>/sessions/<project>/session.jsonl
        Legacy format:    ~/.opencode/sessions/<project>/session.jsonl

        Returns the immediate parent directory name, or "" when the parent is a
        known non-project directory (sessions, agents).
        """
        parent = os.path.basename(os.path.dirname(file_path))
        if parent in {"sessions", "agents"}:
            return ""
        return parent
