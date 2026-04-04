"""ChatGPT export adapter.

Parses ``conversations.json`` from OpenAI data export (Settings → Export data).
Format: top-level JSON array. Each conversation has a ``mapping`` dict of
tree-structured nodes with ``parent``/``children`` references.
User messages: ``node["message"]["author"]["role"] == "user"``.
Content: ``node["message"]["content"]["parts"]`` — list of strings, joined.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ctxray.adapters.base import BaseAdapter
from ctxray.adapters.filters import should_keep_prompt
from ctxray.core.conversation import ConversationTurn
from ctxray.core.models import Prompt

logger = logging.getLogger(__name__)

# Warn when file exceeds this size (200 MB)
_LARGE_FILE_THRESHOLD = 200 * 1024 * 1024


class ChatGPTAdapter(BaseAdapter):
    """Adapter for ChatGPT conversations.json export files."""

    name = "chatgpt-export"
    default_session_path = "~"  # Not auto-discovered; used via `ctxray import`

    def detect_installed(self) -> bool:
        """ChatGPT exports are explicit files — never auto-detected."""
        return False

    def parse_session(self, path: Path) -> list[Prompt]:
        """Parse a ChatGPT conversations.json file into Prompt objects."""
        try:
            file_size = Path(path).stat().st_size
            if file_size > _LARGE_FILE_THRESHOLD:
                logger.warning(
                    "Large file (%d MB): %s — this may use significant memory",
                    file_size // (1024 * 1024),
                    path,
                )
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []

        if not isinstance(data, list):
            return []

        prompts: list[Prompt] = []
        for conversation in data:
            title = conversation.get("title", "untitled")
            mapping = conversation.get("mapping", {})
            conv_id = _make_session_id(conversation)

            # Collect user messages sorted by create_time
            user_nodes = []
            for node in mapping.values():
                msg = node.get("message")
                if msg is None:
                    continue
                author = msg.get("author", {})
                if author.get("role") != "user":
                    continue
                user_nodes.append(msg)

            user_nodes.sort(key=lambda m: m.get("create_time") or 0)

            for msg in user_nodes:
                text = _extract_content(msg)
                if not should_keep_prompt(text):
                    continue
                prompts.append(
                    Prompt(
                        text=text,
                        source=self.name,
                        session_id=conv_id,
                        project=title,
                        timestamp=_format_timestamp(msg.get("create_time")),
                    )
                )

        return prompts

    def parse_conversation(self, path: Path, conv_id: str | None = None) -> list[ConversationTurn]:
        """Parse a single conversation with both user and assistant turns.

        Args:
            path: Path to conversations.json file.
            conv_id: If given, select the conversation matching this ID.
                     If None, parse the first conversation in the file.
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []

        if not isinstance(data, list) or not data:
            return []

        # Select conversation
        conversation = None
        if conv_id:
            for conv in data:
                if _make_session_id(conv) == conv_id:
                    conversation = conv
                    break
            if conversation is None:
                return []
        else:
            conversation = data[0]

        mapping = conversation.get("mapping", {})

        # Collect all messages (user + assistant) sorted by create_time
        all_nodes = []
        for node in mapping.values():
            msg = node.get("message")
            if msg is None:
                continue
            author = msg.get("author", {})
            role = author.get("role", "")
            if role not in ("user", "assistant"):
                continue
            all_nodes.append((role, msg))

        all_nodes.sort(key=lambda x: x[1].get("create_time") or 0)

        turns: list[ConversationTurn] = []
        for i, (role, msg) in enumerate(all_nodes):
            text = _extract_content(msg)
            if not text.strip():
                continue
            turns.append(
                ConversationTurn(
                    role=role,
                    text=text,
                    timestamp=_format_timestamp(msg.get("create_time")),
                    turn_index=i,
                )
            )

        return turns


def _make_session_id(conversation: dict) -> str:
    """Create a stable session ID from conversation create_time + title hash."""
    ct = conversation.get("create_time")
    title = conversation.get("title", "untitled")
    suffix = hashlib.sha256(title.encode()).hexdigest()[:8]
    if ct:
        dt = datetime.fromtimestamp(ct, tz=timezone.utc)
        return f"chatgpt-{dt.strftime('%Y%m%dT%H%M%S')}-{suffix}"
    return f"chatgpt-{suffix}"


def _extract_content(message: dict) -> str:
    """Extract text from message content parts."""
    content = message.get("content", {})
    parts = content.get("parts", [])
    # Parts can contain strings or dicts (for image/file refs) — keep only strings
    text_parts = [p for p in parts if isinstance(p, str)]
    return "".join(text_parts).strip()


def _format_timestamp(create_time: float | None) -> str:
    """Convert Unix timestamp to ISO-like string."""
    if not create_time:
        return ""
    dt = datetime.fromtimestamp(create_time, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
