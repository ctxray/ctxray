"""Message handler for Native Messaging bridge.

Processes incoming messages from the browser extension:
- ping -> pong (health check)
- sync_prompts -> store in DB, return counts
- get_status -> return DB stats
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from reprompt import __version__
from reprompt.adapters.filters import should_keep_prompt
from reprompt.storage.db import PromptDB


def handle_message(message: dict[str, Any], db: PromptDB) -> dict[str, Any]:
    """Process a single message and return a response dict."""
    msg_type = message.get("type", "")

    if msg_type == "ping":
        return {"type": "pong", "version": __version__}

    if msg_type == "sync_prompts":
        return _handle_sync(message, db)

    if msg_type == "get_status":
        return _handle_status(db)

    return {"type": "error", "message": f"Unknown message type: {msg_type}"}


def _handle_sync(message: dict[str, Any], db: PromptDB) -> dict[str, Any]:
    """Store synced prompts in DB, skipping noise and duplicates."""
    prompts = message.get("prompts", [])
    received = len(prompts)
    new_stored = 0
    duplicates = 0

    for p in prompts:
        text = p.get("text", "").strip()
        if not should_keep_prompt(text):
            continue

        source = p.get("source", "extension")
        session_id = p.get("conversation_id", "")
        project = p.get("conversation_title", "")
        timestamp = p.get("timestamp", "")

        inserted = db.insert_prompt(
            text,
            source=source,
            project=project,
            session_id=session_id,
            timestamp=timestamp,
        )
        if inserted:
            new_stored += 1
        else:
            duplicates += 1

    # Record last sync time
    _update_last_sync(db)

    return {
        "type": "sync_result",
        "received": received,
        "new_stored": new_stored,
        "duplicates": duplicates,
    }


def _handle_status(db: PromptDB) -> dict[str, Any]:
    """Return current database stats."""
    stats = db.get_stats()
    return {
        "type": "status",
        "total_prompts": stats.get("total_prompts", 0),
        "last_sync": _get_last_sync(db),
        "version": __version__,
    }


def _update_last_sync(db: PromptDB) -> None:
    """Store last sync timestamp in the DB metadata.

    Uses term_stats table with sentinel key. Stores Unix timestamp in count column.
    """
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    conn = db._conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO term_stats (term, count, df, tfidf_avg) VALUES (?, ?, ?, ?)",
            ("__last_extension_sync__", now_ts, 0, 0.0),
        )
        conn.commit()
    finally:
        conn.close()


def _get_last_sync(db: PromptDB) -> str:
    """Get last sync timestamp. Returns empty string if never synced."""
    conn = db._conn()
    try:
        row = conn.execute(
            "SELECT count FROM term_stats WHERE term = '__last_extension_sync__'"
        ).fetchone()
        if row and row["count"]:
            return datetime.fromtimestamp(row["count"], tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        return ""
    finally:
        conn.close()
