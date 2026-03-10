"""OpenClaw/OpenCode session adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.claude_code import should_keep_prompt
from reprompt.core.models import Prompt


class OpenClawAdapter(BaseAdapter):
    """Adapter for OpenClaw/OpenCode JSONL session files.

    OpenClaw sessions use a simpler format than Claude Code:
    - No 'type' wrapper -- directly has 'role' field
    - 'content' is always a string (not list)
    - Session path: ~/.opencode/sessions/
    """

    name = "openclaw"
    default_session_path = "~/.opencode/sessions"

    def __init__(self, session_path: Path | None = None) -> None:
        self._session_path = session_path or Path(
            os.path.expanduser(self.default_session_path)
        )

    def detect_installed(self) -> bool:
        """Check if OpenClaw session directory exists."""
        return self._session_path.is_dir()

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
        """Extract project name from OpenClaw session path.

        Path format: ~/.opencode/sessions/<project-name>/session.jsonl
        """
        parent = os.path.basename(os.path.dirname(file_path))
        if parent == "sessions":
            return ""
        return parent
