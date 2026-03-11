"""Claude Code session adapter."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt  # noqa: F401 — re-exported
from reprompt.core.models import Prompt
from reprompt.core.session_meta import SessionMeta

# Regex patterns for IDE-injected prefixes that wrap real user prompts.
# We strip these prefixes and keep the actual question after the closing tag.
IDE_PREFIX_RE = re.compile(
    r"^(?:<ide_opened_file>.*?</ide_opened_file>\s*"
    r"|<ide_selection>[\s\S]*?</ide_selection>\s*)+",
)


def _extract_text(message: dict[str, object]) -> str:
    """Extract text from a message, handling both string and list content.

    Strips IDE-injected prefixes (``<ide_opened_file>``, ``<ide_selection>``)
    so the real user question is preserved.
    """
    content = message.get("content", "")
    if isinstance(content, list):
        parts = [
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        ]
        raw = " ".join(parts).strip()
    else:
        raw = str(content).strip()

    # Strip IDE prefix blocks — keep the real prompt after the closing tag
    cleaned = IDE_PREFIX_RE.sub("", raw).strip()
    return cleaned if cleaned else raw


class ClaudeCodeAdapter(BaseAdapter):
    """Adapter for Claude Code JSONL session files."""

    name = "claude-code"
    default_session_path = "~/.claude/projects"

    def __init__(self, session_path: Path | None = None) -> None:
        self._session_path = session_path or Path(os.path.expanduser(self.default_session_path))

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

    def parse_session_meta(self, path: Path) -> SessionMeta | None:
        """Extract session metadata from JSONL by reading all entries."""
        from reprompt.core.effectiveness import detect_final_status
        from reprompt.core.session_meta import SessionMeta

        entries: list[dict[str, object]] = []
        timestamps: list[str] = []
        tool_calls = 0
        error_count = 0
        prompt_lengths: list[int] = []
        prompt_count = 0

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

                msg = entry.get("message", {})
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "")

                if role == "user":
                    text = _extract_text(msg)
                    if should_keep_prompt(text):
                        prompt_count += 1
                        prompt_lengths.append(len(text))
                elif role == "assistant":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "tool_use":
                                    tool_calls += 1
                                text_block = str(block.get("text", ""))
                                if any(
                                    p in text_block
                                    for p in ("Error", "error", "traceback", "Traceback")
                                ):
                                    error_count += 1
                    elif isinstance(content, str):
                        if any(p in content for p in ("Error", "error", "traceback", "Traceback")):
                            error_count += 1

        if not entries or prompt_count == 0:
            return None

        start = timestamps[0] if timestamps else ""
        end = timestamps[-1] if timestamps else ""

        # Duration
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
            session_id=path.stem,
            source=self.name,
            project=self._project_from_path(str(path)),
            start_time=start,
            end_time=end,
            duration_seconds=duration,
            prompt_count=prompt_count,
            tool_call_count=tool_calls,
            error_count=error_count,
            final_status=detect_final_status(entries),
            avg_prompt_length=(
                sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0.0
            ),
        )

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
