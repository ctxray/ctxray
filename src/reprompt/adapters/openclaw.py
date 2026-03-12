"""OpenClaw/OpenCode session adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt
from reprompt.core.models import Prompt

if TYPE_CHECKING:
    from reprompt.core.session_meta import SessionMeta

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

    def parse_session_meta(self, path: Path) -> SessionMeta | None:
        """Extract session metadata from an OpenClaw JSONL session.

        OpenClaw format stores role/content/timestamp directly on each entry
        (no 'message' wrapper). Content is always a string, so tool calls
        are not detectable — tool_call_count is always 0.
        """
        from reprompt.core.effectiveness import detect_final_status
        from reprompt.core.session_meta import SessionMeta

        entries: list[dict[str, object]] = []
        timestamps: list[str] = []
        error_count = 0
        prompt_lengths: list[int] = []
        prompt_count = 0
        session_id = path.stem  # fallback if not in data

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(entry)

                ts = entry.get("timestamp", "")
                if ts:
                    timestamps.append(str(ts))

                # Prefer session_id from data over filename stem
                if "session_id" in entry:
                    session_id = str(entry["session_id"])

                role = entry.get("role", "")
                text = str(entry.get("content", "")).strip()

                if role == "user":
                    if should_keep_prompt(text):
                        prompt_count += 1
                        prompt_lengths.append(len(text))
                elif role == "assistant":
                    if any(p in text for p in ("Error", "error", "traceback", "Traceback")):
                        error_count += 1

        if not entries or prompt_count == 0:
            return None

        start = timestamps[0] if timestamps else ""
        end = timestamps[-1] if timestamps else ""

        duration = 0
        if start and end:
            from datetime import datetime

            try:
                t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(end.replace("Z", "+00:00"))
                duration = max(0, int((t1 - t0).total_seconds()))
            except (ValueError, TypeError):
                pass

        return SessionMeta(
            session_id=session_id,
            source=self.name,
            project=self._project_from_path(str(path)),
            start_time=start,
            end_time=end,
            duration_seconds=duration,
            prompt_count=prompt_count,
            tool_call_count=0,  # not detectable from string content
            error_count=error_count,
            final_status=detect_final_status(entries),
            avg_prompt_length=(
                sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0.0
            ),
        )

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
