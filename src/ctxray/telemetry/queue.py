"""SQLite-backed telemetry event queue.

Events are stored locally and batch-sent when the user runs a command.
Failed sends stay in queue for the next attempt. Events older than 30 days
are automatically discarded.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


class TelemetryQueue:
    """FIFO queue for telemetry events, backed by SQLite."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS telemetry_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_tq_created
                    ON telemetry_queue (created_at);
            """)
            conn.commit()
        finally:
            conn.close()

    def enqueue(self, payload_json: str) -> None:
        """Add an event payload (JSON string) to the queue."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO telemetry_queue (payload, created_at) VALUES (?, ?)",
                (payload_json, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def dequeue(self, limit: int = 50) -> list[tuple[int, str]]:
        """Return up to ``limit`` oldest events as (id, payload_json) tuples."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, payload FROM telemetry_queue ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(row["id"], row["payload"]) for row in rows]
        finally:
            conn.close()

    def acknowledge(self, ids: list[int]) -> None:
        """Remove successfully sent events by their IDs."""
        if not ids:
            return
        conn = self._conn()
        try:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"DELETE FROM telemetry_queue WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()
        finally:
            conn.close()

    def pending_count(self) -> int:
        """Return the number of events waiting to be sent."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) FROM telemetry_queue").fetchone()
            return int(row[0])
        finally:
            conn.close()

    def flush_old(self, max_age_days: int = 30) -> int:
        """Remove events older than *max_age_days*.  Returns count removed."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM telemetry_queue WHERE created_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
