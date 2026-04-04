"""Tests for DB schema version tracking."""

from __future__ import annotations

import sqlite3

import pytest

from ctxray.storage.db import PromptDB


@pytest.fixture
def db(tmp_path):
    return PromptDB(tmp_path / "test.db")


def test_new_db_has_current_schema_version(db):
    """Fresh DB gets the latest schema version."""
    conn = sqlite3.connect(str(db.path))
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert version >= 2  # v1=initial, v2=v0.8 effectiveness columns


def test_schema_version_survives_reopen(tmp_path):
    """Schema version persists across PromptDB instantiations."""
    PromptDB(tmp_path / "test.db")
    db2 = PromptDB(tmp_path / "test.db")
    conn = sqlite3.connect(str(db2.path))
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert version >= 2


def test_migration_from_v0_adds_effectiveness_columns(tmp_path):
    """Simulated pre-v0.8 DB (user_version=0) gains effectiveness columns after migration."""
    # Create a bare DB with tables but no effectiveness columns
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 0")
    conn.executescript("""
        CREATE TABLE prompts (
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
            duplicate_of INTEGER
        );
        CREATE TABLE prompt_patterns (
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
        CREATE TABLE processed_sessions (
            file_path TEXT PRIMARY KEY, processed_at TEXT, source TEXT
        );
        CREATE TABLE term_stats (term TEXT PRIMARY KEY, count INTEGER, df INTEGER, tfidf_avg REAL);
        CREATE TABLE prompt_snapshots (
            id INTEGER PRIMARY KEY, window_start TEXT, window_end TEXT,
            window_label TEXT, period TEXT, prompt_count INTEGER, unique_count INTEGER,
            avg_length REAL, median_length REAL, vocab_size INTEGER,
            specificity_score REAL, category_distribution TEXT, top_terms TEXT, computed_at TEXT
        );
        CREATE TABLE session_meta (
            session_id TEXT PRIMARY KEY, source TEXT, project TEXT,
            start_time TEXT, end_time TEXT, duration_seconds INTEGER,
            prompt_count INTEGER, tool_call_count INTEGER, error_count INTEGER,
            final_status TEXT, avg_prompt_length REAL, effectiveness_score REAL, scanned_at TEXT
        );
        CREATE TABLE prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, text TEXT,
            category TEXT DEFAULT 'other', usage_count INTEGER DEFAULT 0, created_at TEXT
        );
        CREATE TABLE prompt_features (
            prompt_hash TEXT PRIMARY KEY, features_json TEXT, overall_score REAL,
            task_type TEXT, computed_at TEXT
        );
        CREATE TABLE digest_log (
            id INTEGER PRIMARY KEY, period TEXT, window_start TEXT, window_end TEXT,
            generated_at TEXT, summary TEXT
        );
    """)
    conn.commit()
    conn.close()

    # Open with PromptDB — should auto-migrate
    PromptDB(db_path)

    conn = sqlite3.connect(str(db_path))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(prompts)").fetchall()]
    pattern_cols = [r[1] for r in conn.execute("PRAGMA table_info(prompt_patterns)").fetchall()]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()

    assert "effectiveness_score" in cols
    assert "effectiveness_avg" in pattern_cols
    assert "effectiveness_sample_size" in pattern_cols
    assert version >= 2


def test_idempotent_migration(tmp_path):
    """Opening PromptDB multiple times doesn't error or change schema."""
    db1 = PromptDB(tmp_path / "test.db")
    conn1 = sqlite3.connect(str(db1.path))
    v1 = conn1.execute("PRAGMA user_version").fetchone()[0]
    cols1 = [r[1] for r in conn1.execute("PRAGMA table_info(prompts)").fetchall()]
    conn1.close()

    db2 = PromptDB(tmp_path / "test.db")
    conn2 = sqlite3.connect(str(db2.path))
    v2 = conn2.execute("PRAGMA user_version").fetchone()[0]
    cols2 = [r[1] for r in conn2.execute("PRAGMA table_info(prompts)").fetchall()]
    conn2.close()

    assert v1 == v2
    assert cols1 == cols2
