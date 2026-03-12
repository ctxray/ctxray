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
        self._migrate_v08()

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
                CREATE TABLE IF NOT EXISTS prompt_snapshots (
                    id INTEGER PRIMARY KEY,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    window_label TEXT,
                    period TEXT NOT NULL,
                    prompt_count INTEGER NOT NULL,
                    unique_count INTEGER NOT NULL,
                    avg_length REAL,
                    median_length REAL,
                    vocab_size INTEGER,
                    specificity_score REAL,
                    category_distribution TEXT,
                    top_terms TEXT,
                    computed_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_window
                    ON prompt_snapshots (window_start, period);
                CREATE TABLE IF NOT EXISTS session_meta (
                    session_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    project TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds INTEGER,
                    prompt_count INTEGER,
                    tool_call_count INTEGER,
                    error_count INTEGER,
                    final_status TEXT,
                    avg_prompt_length REAL,
                    effectiveness_score REAL,
                    scanned_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    text TEXT NOT NULL,
                    category TEXT DEFAULT 'other',
                    usage_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prompt_features (
                    prompt_hash TEXT PRIMARY KEY,
                    features_json TEXT NOT NULL,
                    overall_score REAL,
                    task_type TEXT,
                    computed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_features_task ON prompt_features (task_type);
                CREATE INDEX IF NOT EXISTS idx_features_score ON prompt_features (overall_score);
                CREATE TABLE IF NOT EXISTS digest_log (
                    id INTEGER PRIMARY KEY,
                    period TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    summary TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _migrate_v08(self) -> None:
        """Add effectiveness columns to existing tables (v0.8.0).
        Uses try/except OperationalError because ALTER TABLE ADD COLUMN
        fails if the column already exists (SQLite < 3.37).
        """
        conn = self._conn()
        try:
            for stmt in [
                "ALTER TABLE prompts ADD COLUMN effectiveness_score REAL",
                "ALTER TABLE prompt_patterns ADD COLUMN effectiveness_avg REAL",
                "ALTER TABLE prompt_patterns ADD COLUMN effectiveness_sample_size INTEGER DEFAULT 0",  # noqa: E501
            ]:
                try:
                    conn.execute(stmt)
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # column already exists
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

    def update_prompt_effectiveness(self, session_id: str, score: float) -> None:
        """Set effectiveness_score on all prompts from a given session."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE prompts SET effectiveness_score = ? WHERE session_id = ?",
                (score, session_id),
            )
            conn.commit()
        finally:
            conn.close()

    def compute_pattern_effectiveness(self) -> None:
        """Update effectiveness_avg and effectiveness_sample_size for all patterns.
        For each pattern, finds prompts whose text contains the pattern text
        (LIKE match) and averages their effectiveness_score.
        Only updates patterns that have at least one matching scored prompt.
        """
        conn = self._conn()
        try:
            conn.execute("""
                UPDATE prompt_patterns
                SET
                  effectiveness_avg = (
                    SELECT AVG(p.effectiveness_score)
                    FROM prompts p
                    WHERE p.text LIKE '%' || prompt_patterns.pattern_text || '%'
                      AND p.effectiveness_score IS NOT NULL
                  ),
                  effectiveness_sample_size = (
                    SELECT COUNT(DISTINCT p.session_id)
                    FROM prompts p
                    WHERE p.text LIKE '%' || prompt_patterns.pattern_text || '%'
                      AND p.effectiveness_score IS NOT NULL
                  )
                WHERE EXISTS (
                  SELECT 1 FROM prompts p
                  WHERE p.text LIKE '%' || prompt_patterns.pattern_text || '%'
                    AND p.effectiveness_score IS NOT NULL
                )
            """)
            conn.commit()
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

    def purge_all(self) -> int:
        """Delete ALL prompts and reset session tracking. Returns count deleted."""
        conn = self._conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM prompts")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM prompts")
            conn.execute("DELETE FROM processed_sessions")
            conn.execute("DELETE FROM prompt_patterns")
            conn.execute("DELETE FROM term_stats")
            conn.commit()
            return count
        finally:
            conn.close()

    def search_prompts(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search prompts by keyword (case-insensitive LIKE match on text).

        Returns matching prompts ordered by timestamp descending.
        """
        conn = self._conn()
        try:
            sql = "SELECT * FROM prompts WHERE duplicate_of IS NULL AND text LIKE ? COLLATE NOCASE"
            params: list[Any] = [f"%{query}%"]

            if category:
                sql += " AND id IN (SELECT p.id FROM prompts p WHERE p.text LIKE ? COLLATE NOCASE)"

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_prompts_in_range(
        self, start: str, end: str, *, unique_only: bool = True
    ) -> list[dict[str, Any]]:
        """Return prompts with timestamp >= start AND < end (ISO-8601 strings).

        If unique_only is True (default), excludes duplicates.
        """
        conn = self._conn()
        try:
            where = "timestamp >= ? AND timestamp < ? AND timestamp != ''"
            if unique_only:
                where += " AND duplicate_of IS NULL"
            rows = conn.execute(
                f"SELECT * FROM prompts WHERE {where} ORDER BY timestamp",
                (start, end),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def upsert_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Insert or update a prompt_snapshot row keyed on (window_start, period)."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO prompt_snapshots
                   (window_start, window_end, window_label, period,
                    prompt_count, unique_count, avg_length, median_length,
                    vocab_size, specificity_score, category_distribution,
                    top_terms, computed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(window_start, period) DO UPDATE SET
                     window_end = excluded.window_end,
                     window_label = excluded.window_label,
                     prompt_count = excluded.prompt_count,
                     unique_count = excluded.unique_count,
                     avg_length = excluded.avg_length,
                     median_length = excluded.median_length,
                     vocab_size = excluded.vocab_size,
                     specificity_score = excluded.specificity_score,
                     category_distribution = excluded.category_distribution,
                     top_terms = excluded.top_terms,
                     computed_at = excluded.computed_at""",
                (
                    snapshot["window_start"],
                    snapshot["window_end"],
                    snapshot.get("window_label", ""),
                    snapshot["period"],
                    snapshot["prompt_count"],
                    snapshot["unique_count"],
                    snapshot.get("avg_length"),
                    snapshot.get("median_length"),
                    snapshot.get("vocab_size"),
                    snapshot.get("specificity_score"),
                    json.dumps(snapshot.get("category_distribution", {})),
                    json.dumps(snapshot.get("top_terms", [])),
                    snapshot["computed_at"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_snapshots(self, period: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent snapshots for a given period, newest first."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM prompt_snapshots
                   WHERE period = ?
                   ORDER BY window_start DESC LIMIT ?""",
                (period, limit),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["category_distribution"] = json.loads(d["category_distribution"] or "{}")
                d["top_terms"] = json.loads(d["top_terms"] or "[]")
                result.append(d)
            return list(reversed(result))  # chronological order
        finally:
            conn.close()

    def upsert_session_meta(
        self,
        session_id: str,
        source: str,
        project: str,
        start_time: str,
        end_time: str,
        duration_seconds: int,
        prompt_count: int,
        tool_call_count: int,
        error_count: int,
        final_status: str,
        avg_prompt_length: float,
        effectiveness_score: float,
    ) -> None:
        """Insert or update session metadata."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO session_meta
                   (session_id, source, project, start_time, end_time,
                    duration_seconds, prompt_count, tool_call_count, error_count,
                    final_status, avg_prompt_length, effectiveness_score, scanned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     effectiveness_score = excluded.effectiveness_score,
                     scanned_at = excluded.scanned_at""",
                (
                    session_id,
                    source,
                    project,
                    start_time,
                    end_time,
                    duration_seconds,
                    prompt_count,
                    tool_call_count,
                    error_count,
                    final_status,
                    avg_prompt_length,
                    effectiveness_score,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_session_meta(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent session metadata ordered by effectiveness."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM session_meta
                   ORDER BY effectiveness_score DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_effectiveness_summary(self) -> dict[str, Any]:
        """Return aggregate effectiveness stats."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) as total,
                          AVG(effectiveness_score) as avg_score,
                          MIN(effectiveness_score) as min_score,
                          MAX(effectiveness_score) as max_score
                   FROM session_meta"""
            ).fetchone()
            return dict(row) if row else {}
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

    def save_template(self, name: str, text: str, category: str = "other") -> int:
        """Save a prompt template. Returns the template ID."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO prompt_templates (name, text, category, created_at)"
                " VALUES (?, ?, ?, ?)",
                (name, text, category, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            return cur.lastrowid or 0
        finally:
            conn.close()

    def list_templates(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all prompt templates, optionally filtered by category."""
        conn = self._conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM prompt_templates WHERE category = ?"
                    " ORDER BY usage_count DESC, id",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM prompt_templates ORDER BY usage_count DESC, id"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_template(self, name: str) -> dict[str, Any] | None:
        """Get a template by name."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM prompt_templates WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def template_name_exists(self, name: str) -> bool:
        """Check if a template name already exists."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT 1 FROM prompt_templates WHERE name = ?", (name,)).fetchone()
            return row is not None
        finally:
            conn.close()

    # -- prompt_features (PromptDNA) -----------------------------------------

    def store_features(self, prompt_hash: str, features: dict[str, Any]) -> None:
        """Store or update PromptDNA features for a prompt."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO prompt_features
                   (prompt_hash, features_json, overall_score,
                    task_type, computed_at)
                   VALUES (?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(prompt_hash) DO UPDATE SET
                     features_json = excluded.features_json,
                     overall_score = excluded.overall_score,
                     task_type = excluded.task_type,
                     computed_at = excluded.computed_at""",
                (
                    prompt_hash,
                    json.dumps(features),
                    features.get("overall_score", 0.0),
                    features.get("task_type", "other"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_features(self, prompt_hash: str) -> dict[str, Any] | None:
        """Retrieve PromptDNA features for a prompt. Returns None if not found."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT features_json FROM prompt_features WHERE prompt_hash = ?",
                (prompt_hash,),
            ).fetchone()
            if row is None:
                return None
            result: dict[str, Any] = json.loads(row["features_json"])
            return result
        finally:
            conn.close()

    def get_all_features(self) -> list[dict[str, Any]]:
        """Return all stored feature vectors."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT features_json FROM prompt_features ORDER BY overall_score DESC"
            ).fetchall()
            return [json.loads(r["features_json"]) for r in rows]
        finally:
            conn.close()

    def get_features_by_task_type(self, task_type: str) -> list[dict[str, Any]]:
        """Return feature vectors filtered by task type."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT features_json FROM prompt_features"
                " WHERE task_type = ? ORDER BY overall_score DESC",
                (task_type,),
            ).fetchall()
            return [json.loads(r["features_json"]) for r in rows]
        finally:
            conn.close()

    # -- digest_log ---------------------------------------------------------

    def log_digest(
        self,
        period: str,
        window_start: str,
        window_end: str,
        summary: str,
    ) -> None:
        """Record that a digest was generated."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO digest_log
                   (period, window_start, window_end, generated_at, summary)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    period,
                    window_start,
                    window_end,
                    datetime.now(timezone.utc).isoformat(),
                    summary,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_last_digest(self, period: str) -> dict[str, Any] | None:
        """Return the most recent digest log entry for a given period."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT * FROM digest_log
                   WHERE period = ?
                   ORDER BY generated_at DESC LIMIT 1""",
                (period,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
