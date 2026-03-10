"""Claude Code session adapter."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.core.models import Prompt

SKIP_EXACT = {
    "\u597d\u7684", "OK", "ok", "Ok", "\u662f\u7684", "\u53ef\u4ee5",
    "sure", "Sure", "yes", "Yes",
    "Done", "done", "Sent", "sent",
    "\u597d", "\u5bf9", "\u884c", "\u55ef",
    "Tool loaded.", "1", "2", "3", "A", "B", "C", "D",
}

SKIP_PREFIXES = (
    "<local-command",
    "<command-name>",
    "Tool loaded",
    "Base directory for this skill",
)


def should_keep_prompt(text: str) -> bool:
    """Filter out noise prompts -- short messages, exact matches, prefixes."""
    text = text.strip()
    if len(text) < 10:
        return False
    if text in SKIP_EXACT:
        return False
    if any(text.startswith(p) for p in SKIP_PREFIXES):
        return False
    if not re.search(r"[a-zA-Z\u4e00-\u9fff]", text):
        return False
    return True


def _extract_text(message: dict) -> str:
    """Extract text from a message, handling both string and list content."""
    content = message.get("content", "")
    if isinstance(content, list):
        parts = [
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        return " ".join(parts).strip()
    return str(content).strip()


class ClaudeCodeAdapter(BaseAdapter):
    """Adapter for Claude Code JSONL session files."""

    name = "claude-code"
    default_session_path = "~/.claude/projects"

    def __init__(self, session_path: Path | None = None) -> None:
        self._session_path = session_path or Path(
            os.path.expanduser(self.default_session_path)
        )

    def detect_installed(self) -> bool:
        """Check if Claude Code session directory exists."""
        return self._session_path.is_dir()

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a Claude Code JSONL session file into Prompt objects."""
        prompts: list[Prompt] = []
        session_id = path.stem

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
                if entry.get("type") != "user":
                    continue

                message = entry.get("message", {})
                if message.get("role") != "user":
                    continue

                text = _extract_text(message)
                if not should_keep_prompt(text):
                    continue

                project = self._project_from_path(str(path))
                timestamp = entry.get("timestamp", "")

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
        """Extract project name from Claude Code session path.

        Path format: ~/.claude/projects/-Users-chris-projects-myproject/session.jsonl
        The parent directory name has dashes replacing path separators.
        """
        parent = os.path.basename(os.path.dirname(file_path))
        parts = parent.split("-")
        for i, p in enumerate(parts):
            if p == "projects" and i + 1 < len(parts):
                return "-".join(parts[i + 1 :])
        return parent
