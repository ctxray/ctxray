"""Claude Code session adapter."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from reprompt.adapters.base import BaseAdapter
from reprompt.adapters.filters import should_keep_prompt  # noqa: F401 — re-exported
from reprompt.core.models import Prompt
from reprompt.core.session_meta import SessionMeta

if TYPE_CHECKING:
    from reprompt.core.conversation import ConversationTurn

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

    def parse_conversation(self, path: Path) -> list[ConversationTurn]:
        """Parse full conversation including assistant turns from JSONL."""
        from reprompt.core.conversation import ConversationTurn

        turns: list[ConversationTurn] = []
        turn_index = 0

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type")
                if entry_type not in ("user", "assistant"):
                    continue

                message = entry.get("message", {})
                if not isinstance(message, dict):
                    continue
                role = message.get("role", "")
                if role not in ("user", "assistant"):
                    continue

                timestamp = str(entry.get("timestamp", ""))

                if role == "user":
                    text = _extract_text(message)
                    if not text.strip():
                        continue
                    turns.append(
                        ConversationTurn(
                            role="user",
                            text=text,
                            timestamp=timestamp,
                            turn_index=turn_index,
                        )
                    )
                    turn_index += 1

                elif role == "assistant":
                    content = message.get("content", "")
                    text_parts: list[str] = []
                    tool_call_count = 0
                    tool_paths: list[str] = []
                    has_error = False

                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            block_type = block.get("type", "")
                            if block_type == "text":
                                t = str(block.get("text", ""))
                                text_parts.append(t)
                                if any(
                                    kw in t
                                    for kw in ("Error", "error", "traceback", "Traceback")
                                ):
                                    has_error = True
                            elif block_type == "tool_use":
                                tool_call_count += 1
                                name = block.get("name", "")
                                inp = block.get("input", {})
                                if isinstance(inp, dict) and name in ("Edit", "Write"):
                                    fp = inp.get("file_path", "")
                                    if fp:
                                        tool_paths.append(fp)
                    elif isinstance(content, str):
                        text_parts.append(content)
                        if any(
                            kw in content
                            for kw in ("Error", "error", "traceback", "Traceback")
                        ):
                            has_error = True

                    text = " ".join(text_parts).strip()
                    if not text and tool_call_count == 0:
                        continue

                    turns.append(
                        ConversationTurn(
                            role="assistant",
                            text=text,
                            timestamp=timestamp,
                            turn_index=turn_index,
                            tool_calls=tool_call_count,
                            has_error=has_error,
                            tool_use_paths=tool_paths,
                        )
                    )
                    turn_index += 1

        return turns

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

        Handles two cases:
        - Main sessions: ~/.claude/projects/-Users-chris-projects-myproject/session.jsonl
        - Subagent sessions: ~/.claude/projects/-Users-chris-projects-myproject/
          {uuid}/subagents/agent-*.jsonl
          → returns "myproject [subagent]"
        """
        path = Path(file_path)
        # Detect subagent sessions: the parent dir is named "subagents"
        if path.parent.name == "subagents":
            # Go up: subagents/ → {session-uuid}/ → {project-dir}/
            project_dir = path.parent.parent.parent.name
            return self._project_name_from_dir(project_dir) + " [subagent]"
        parent = path.parent.name
        return self._project_name_from_dir(parent)

    def _project_name_from_dir(self, dir_name: str) -> str:
        """Convert a dash-encoded directory name to a project name."""
        parts = dir_name.split("-")
        for i, p in enumerate(parts):
            if p == "projects" and i + 1 < len(parts):
                return "-".join(parts[i + 1 :])
        return dir_name
