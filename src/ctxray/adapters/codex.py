"""Codex CLI session adapter.

Parses ``rollout-*.jsonl`` files stored under ``~/.codex/sessions/``.
Each JSONL line has a ``type`` + ``payload`` structure with event types:
``session_meta``, ``event_msg`` (user_message, agent_message, error,
token_count, exec_command_end), and ``response_item`` (local_shell_call,
function_call).

Ref: https://github.com/openai/codex
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from ctxray.adapters.base import BaseAdapter
from ctxray.adapters.filters import should_keep_prompt
from ctxray.core.models import Prompt

if TYPE_CHECKING:
    from ctxray.core.conversation import ConversationTurn

_DEFAULT_CODEX_HOME = "~/.codex"


class CodexAdapter(BaseAdapter):
    """Adapter for OpenAI Codex CLI session files."""

    name = "codex"
    default_session_path = _DEFAULT_CODEX_HOME

    def __init__(self, codex_home: Path | None = None) -> None:
        self._home = codex_home or Path(os.path.expanduser(_DEFAULT_CODEX_HOME))

    def detect_installed(self) -> bool:
        return len(self.discover_sessions()) > 0

    def discover_sessions(self) -> list[Path]:
        """Find all rollout-*.jsonl files under ~/.codex/sessions/."""
        sessions_dir = self._home / "sessions"
        if not sessions_dir.is_dir():
            return []
        return sorted(sessions_dir.rglob("rollout-*.jsonl"))

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a Codex CLI rollout JSONL file into Prompt objects."""
        prompts: list[Prompt] = []
        session_id = self._session_id_from_path(path)
        project = ""

        for line_data in self._iter_lines(path):
            # Extract project from session_meta
            if line_data.get("type") == "session_meta":
                payload = line_data.get("payload", {})
                project = payload.get("cwd", "")
                if project:
                    project = project.rsplit("/", 1)[-1]
                continue

            payload = line_data.get("payload", {})
            payload_type = payload.get("type", "")

            if payload_type == "user_message":
                text = payload.get("message", "").strip()
                if not should_keep_prompt(text):
                    continue
                prompts.append(
                    Prompt(
                        text=text,
                        source=self.name,
                        session_id=session_id,
                        project=project,
                        timestamp=line_data.get("timestamp", ""),
                    )
                )

        return prompts

    def parse_conversation(self, path: Path) -> list[ConversationTurn]:
        """Parse full conversation including assistant turns and tool calls."""
        from ctxray.core.conversation import ConversationTurn

        turns: list[ConversationTurn] = []
        turn_index = 0

        # Accumulator for the current assistant turn
        asst_text = ""
        asst_tool_names: list[str] = []
        asst_tool_paths: list[str] = []
        asst_has_error = False
        asst_error_text = ""
        asst_timestamp = ""
        in_assistant_turn = False

        def _flush_assistant() -> None:
            nonlocal turn_index, in_assistant_turn
            nonlocal asst_text, asst_tool_names, asst_tool_paths
            nonlocal asst_has_error, asst_error_text, asst_timestamp

            if not in_assistant_turn:
                return
            if not asst_text and not asst_tool_names:
                in_assistant_turn = False
                return

            turns.append(
                ConversationTurn(
                    role="assistant",
                    text=asst_text.strip(),
                    timestamp=asst_timestamp,
                    turn_index=turn_index,
                    tool_calls=len(asst_tool_names),
                    has_error=asst_has_error,
                    tool_use_paths=asst_tool_paths[:],
                    tool_names=asst_tool_names[:],
                    error_text=asst_error_text,
                )
            )
            turn_index += 1

            # Reset
            asst_text = ""
            asst_tool_names = []
            asst_tool_paths = []
            asst_has_error = False
            asst_error_text = ""
            asst_timestamp = ""
            in_assistant_turn = False

        for line_data in self._iter_lines(path):
            line_type = line_data.get("type", "")
            payload = line_data.get("payload", {})
            payload_type = payload.get("type", "") if isinstance(payload, dict) else ""
            timestamp = line_data.get("timestamp", "")

            # User message → flush assistant, emit user turn
            if payload_type == "user_message":
                _flush_assistant()
                text = payload.get("message", "").strip()
                if not should_keep_prompt(text):
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
                continue

            # Agent message → start or continue assistant turn
            if payload_type == "agent_message":
                if not in_assistant_turn:
                    in_assistant_turn = True
                    asst_timestamp = timestamp
                msg = payload.get("message", "")
                if msg:
                    asst_text += (" " + msg) if asst_text else msg
                continue

            # Tool call: local_shell_call
            if line_type == "response_item" and payload_type == "local_shell_call":
                if not in_assistant_turn:
                    in_assistant_turn = True
                    asst_timestamp = timestamp
                action = payload.get("action", {})
                cmd = action.get("command", [])
                tool_name = cmd[0] if cmd else "shell"
                asst_tool_names.append(tool_name)
                continue

            # Tool call: function_call
            if line_type == "response_item" and payload_type == "function_call":
                if not in_assistant_turn:
                    in_assistant_turn = True
                    asst_timestamp = timestamp
                name = payload.get("name", "function")
                asst_tool_names.append(name)
                continue

            # Command execution result
            if payload_type == "exec_command_end":
                exit_code = payload.get("exit_code", 0)
                if exit_code != 0:
                    asst_has_error = True
                    output = payload.get("aggregated_output", "")
                    if output and not asst_error_text:
                        asst_error_text = output[:200]
                # Track file paths from commands
                cmd = payload.get("command", [])
                for arg in cmd[1:]:
                    if "/" in arg or "." in arg:
                        asst_tool_paths.append(arg)
                        break
                continue

            # Error event
            if payload_type == "error":
                asst_has_error = True
                msg = payload.get("message", "")
                if msg and not asst_error_text:
                    asst_error_text = msg[:200]
                continue

        # Flush final assistant turn
        _flush_assistant()

        return turns

    def _session_id_from_path(self, path: Path) -> str:
        """Extract session ID from rollout filename.

        rollout-2025-05-07T17-24-21-UUID.jsonl → UUID part
        """
        stem = path.stem  # rollout-2025-05-07T17-24-21-UUID
        # Remove 'rollout-' prefix
        rest = stem[len("rollout-") :] if stem.startswith("rollout-") else stem
        # The UUID is the last 36 chars (8-4-4-4-12 format)
        if len(rest) > 36:
            return rest[-36:]
        return rest

    @staticmethod
    def _iter_lines(path: Path):
        """Yield parsed JSON objects from a JSONL file, skipping bad lines."""
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
