"""Aider session adapter.

Parses `.aider.chat.history.md` files — append-only Markdown logs where:
- ``# aider chat started at YYYY-MM-DD HH:MM:SS`` marks a session boundary
- ``#### text`` is a user message
- Bare paragraphs are AI responses (skipped)
- ``> text`` is tool output (skipped)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ctxray.adapters.base import BaseAdapter
from ctxray.adapters.filters import should_keep_prompt
from ctxray.core.models import Prompt

_SESSION_RE = re.compile(r"^# aider chat started at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_USER_MSG_RE = re.compile(r"^#### (.+)")

# Default places to search for aider history files.
# Note: "~" (home root) is intentionally excluded — rglob over ~/Library traverses
# network-mounted paths (OneDrive, iCloud) that can time out on macOS.
_DEFAULT_SEARCH_ROOTS = ("~/projects", "~/repos", "~/code", "~/src", "~/dev", "~/work")


class AiderAdapter(BaseAdapter):
    """Adapter for Aider markdown chat history files.

    Unlike Claude Code/OpenClaw which store sessions under a fixed directory,
    Aider writes ``.aider.chat.history.md`` inside each project's git root.
    The adapter searches configurable root directories for these files.
    """

    name = "aider"
    default_session_path = "~/projects"
    session_filename = ".aider.chat.history.md"

    def __init__(self, search_roots: list[Path] | None = None) -> None:
        if search_roots:
            self._search_roots = search_roots
        else:
            self._search_roots = [Path(os.path.expanduser(r)) for r in _DEFAULT_SEARCH_ROOTS]

    def detect_installed(self) -> bool:
        """Check if any aider chat history files exist."""
        return len(self.discover_sessions()) > 0

    def discover_sessions(self) -> list[Path]:
        """Find all .aider.chat.history.md files under search roots."""
        found: list[Path] = []
        seen: set[str] = set()
        for root in self._search_roots:
            if not root.is_dir():
                continue
            try:
                paths = sorted(root.rglob(self.session_filename))
            except OSError:
                continue
            for p in paths:
                real = str(p.resolve())
                if real not in seen:
                    seen.add(real)
                    found.append(p)
        return found

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse an Aider chat history file into Prompt objects."""
        prompts: list[Prompt] = []
        current_session_id = ""
        current_timestamp = ""
        project = self._project_from_path(str(path))

        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        for line in text.splitlines():
            # Session boundary
            m = _SESSION_RE.match(line)
            if m:
                ts = m.group(1)
                current_timestamp = ts
                current_session_id = ts.replace(" ", "T").replace(":", "-")
                continue

            # User message
            m = _USER_MSG_RE.match(line)
            if m:
                msg = m.group(1).strip()
                if not should_keep_prompt(msg):
                    continue
                prompts.append(
                    Prompt(
                        text=msg,
                        source=self.name,
                        session_id=current_session_id,
                        project=project,
                        timestamp=current_timestamp,
                    )
                )

        return prompts

    def parse_session_with_project(self, path: str) -> list[Prompt]:
        """Parse session, deriving project name from the file path."""
        return self.parse_session(Path(path))

    @staticmethod
    def _project_from_path(path: str) -> str:
        """Extract project name from the parent directory of the history file."""
        parent = Path(path).resolve().parent
        return parent.name
