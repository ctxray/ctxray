"""SQLite storage for prompts, patterns, and term statistics."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class PromptDB:
    """SQLite-backed storage for prompt data."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        """Get a connection with row_factory set."""
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY,
                    hash TEXT UNIQUE,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    project TEXT,
                    session_id TEXT,
                    timestamp TEXT,
                    char_count INTEGER,
                    embedding BLOB,
                    cluster_id INTEGER,
                    duplicate_of INTEGER REFERENCES prompts(id)
                );
                CREATE TABLE IF NOT EXISTS processed_sessions (
                    file_path TEXT PRIMARY KEY,
                    processed_at TEXT,
                    source TEXT
                );
                CREATE TABLE IF NOT EXISTS prompt_patterns (
                    id INTEGER PRIMARY KEY,
                    pattern_text TEXT,
                    frequency INTEGER,
                    avg_length REAL,
                    projects TEXT,
                    category TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    examples TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_patterns_text
                    ON prompt_patterns (pattern_text);
                CREATE TABLE IF NOT EXISTS term_stats (
                    term TEXT PRIMARY KEY,
                    count INTEGER,
                    df INTEGER,
                    tfidf_avg REAL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _hash(text: str) -> str:
        """SHA-256 hash of stripped text."""
        return hashlib.sha256(text.strip().encode()).hexdigest()

    def insert_prompt(
        self,
        text: str,
        *,
        source: str,
        project: str | None = None,
        session_id: str = "",
        timestamp: str = "",
    ) -> bool:
        """Insert a prompt. Returns True if new, False if duplicate by hash."""
        stripped = text.strip()
        h = self._hash(stripped)
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO prompts (hash, text, source, project, session_id,
                   timestamp, char_count) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (h, stripped, source, project, session_id, timestamp, len(stripped)),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_all_prompts(self) -> list[dict[str, Any]]:
        """Return all prompts as dicts."""
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM prompts ORDER BY id").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_prompts_without_embedding(self) -> list[dict[str, Any]]:
        """Return prompts that have no embedding yet."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM prompts WHERE embedding IS NULL AND duplicate_of IS NULL ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_embedding(self, prompt_id: int, embedding: bytes) -> None:
        """Store an embedding blob for a prompt."""
        conn = self._conn()
        try:
            conn.execute("UPDATE prompts SET embedding = ? WHERE id = ?", (embedding, prompt_id))
            conn.commit()
        finally:
            conn.close()

    def mark_duplicate(self, prompt_id: int, duplicate_of: int) -> None:
        """Mark a prompt as a duplicate of another."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE prompts SET duplicate_of = ? WHERE id = ?", (duplicate_of, prompt_id)
            )
            conn.commit()
        finally:
            conn.close()

    def mark_session_processed(self, file_path: str, source: str = "") -> None:
        """Record that a session file has been processed."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO processed_sessions (file_path, processed_at, source) "
                "VALUES (?, ?, ?)",
                (file_path, datetime.now(timezone.utc).isoformat(), source),
            )
            conn.commit()
        finally:
            conn.close()

    def is_session_processed(self, file_path: str) -> bool:
        """Check if a session file has already been processed."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM processed_sessions WHERE file_path = ?", (file_path,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def insert_pattern(
        self,
        pattern_text: str,
        frequency: int,
        avg_length: float,
        projects: list[str],
        category: str,
        first_seen: str,
        last_seen: str,
        examples: list[str],
    ) -> int:
        """Insert a prompt pattern. Returns the new pattern ID."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO prompt_patterns
                   (pattern_text, frequency, avg_length, projects, category,
                    first_seen, last_seen, examples)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pattern_text,
                    frequency,
                    avg_length,
                    json.dumps(projects),
                    category,
                    first_seen,
                    last_seen,
                    json.dumps(examples),
                ),
            )
            conn.commit()
            pattern_id = cursor.lastrowid
            assert pattern_id is not None
            return pattern_id
        finally:
            conn.close()

    def upsert_pattern(
        self,
        pattern_text: str,
        frequency: int,
        avg_length: float,
        projects: list[str],
        category: str,
        first_seen: str,
        last_seen: str,
        examples: list[str],
    ) -> int:
        """Insert or update a pattern keyed on pattern_text. Returns the pattern ID.

        If a pattern with the same text already exists its frequency, avg_length,
        category, last_seen, projects, and examples are updated in place so that
        the row ID (and any external references to it) remains stable.
        """
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO prompt_patterns
                   (pattern_text, frequency, avg_length, projects, category,
                    first_seen, last_seen, examples)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(pattern_text) DO UPDATE SET
                     frequency  = excluded.frequency,
                     avg_length = excluded.avg_length,
                     projects   = excluded.projects,
                     category   = excluded.category,
                     last_seen  = excluded.last_seen,
                     examples   = excluded.examples""",
                (
                    pattern_text,
                    frequency,
                    avg_length,
                    json.dumps(projects),
                    category,
                    first_seen,
                    last_seen,
                    json.dumps(examples),
                ),
            )
            conn.commit()
            # lastrowid returns 0 on the UPDATE path in SQLite; fetch the real id
            row = conn.execute(
                "SELECT id FROM prompt_patterns WHERE pattern_text = ?", (pattern_text,)
            ).fetchone()
            assert row is not None
            return int(row[0])
        finally:
            conn.close()

    def get_patterns(self, category: str | None = None) -> list[dict[str, Any]]:
        """Return all patterns, optionally filtered by category."""
        conn = self._conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM prompt_patterns WHERE category = ? ORDER BY frequency DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM prompt_patterns ORDER BY frequency DESC"
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["projects"] = json.loads(d["projects"]) if d["projects"] else []
                d["examples"] = json.loads(d["examples"]) if d["examples"] else []
                result.append(d)
            return result
        finally:
            conn.close()

    def clear_patterns(self) -> None:
        """Delete all stored patterns (called before re-computing)."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM prompt_patterns")
            conn.commit()
        finally:
            conn.close()

    def upsert_term_stats(self, term: str, count: int, df: int, tfidf_avg: float) -> None:
        """Insert or update term statistics."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO term_stats (term, count, df, tfidf_avg)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(term) DO UPDATE SET
                     count = excluded.count,
                     df = excluded.df,
                     tfidf_avg = excluded.tfidf_avg""",
                (term, count, df, tfidf_avg),
            )
            conn.commit()
        finally:
            conn.close()

    def get_term_stats(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return top terms by count."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM term_stats ORDER BY count DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def purge_old_prompts(self, retention_days: int = 90) -> int:
        """Delete prompts older than retention_days. Returns count deleted.

        Two-pass: first remove duplicates pointing to old prompts,
        then remove the old prompts themselves.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        conn = self._conn()
        try:
            # Pass 1: clear duplicate_of references to soon-deleted prompts
            conn.execute(
                """UPDATE prompts SET duplicate_of = NULL
                   WHERE duplicate_of IN (
                       SELECT id FROM prompts WHERE timestamp < ? AND timestamp != ''
                   )""",
                (cutoff,),
            )
            # Pass 2: delete old prompts
            cursor = conn.execute(
                "DELETE FROM prompts WHERE timestamp < ? AND timestamp != ''",
                (cutoff,),
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            conn.close()

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
            unique = conn.execute(
                "SELECT COUNT(*) FROM prompts WHERE duplicate_of IS NULL"
            ).fetchone()[0]
            sessions = conn.execute("SELECT COUNT(*) FROM processed_sessions").fetchone()[0]
            patterns = conn.execute("SELECT COUNT(*) FROM prompt_patterns").fetchone()[0]
            date_range = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM prompts WHERE timestamp != ''"
            ).fetchone()
            return {
                "total_prompts": total,
                "unique_prompts": unique,
                "sessions_processed": sessions,
                "patterns": patterns,
                "earliest": date_range[0] if date_range else None,
                "latest": date_range[1] if date_range else None,
            }
        finally:
            conn.close()
