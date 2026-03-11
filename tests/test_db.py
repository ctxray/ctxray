"""Tests for SQLite storage layer."""

import sqlite3

import pytest

from reprompt.storage.db import PromptDB


@pytest.fixture
def db(tmp_path):
    return PromptDB(tmp_path / "test.db")


def test_schema_creates_tables(db):
    """All 4 tables exist after init."""
    conn = sqlite3.connect(str(db.path))
    tables = [
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    ]
    assert "prompts" in tables
    assert "processed_sessions" in tables
    assert "prompt_patterns" in tables
    assert "term_stats" in tables


def test_insert_new_prompt(db):
    ok = db.insert_prompt(
        "hello world",
        source="claude-code",
        project="test",
        session_id="s1",
        timestamp="2026-01-01T00:00:00Z",
    )
    assert ok is True


def test_insert_exact_dupe(db):
    db.insert_prompt(
        "hello world",
        source="claude-code",
        project="test",
        session_id="s1",
        timestamp="2026-01-01T00:00:00Z",
    )
    ok = db.insert_prompt(
        "hello world",
        source="claude-code",
        project="test",
        session_id="s2",
        timestamp="2026-01-02T00:00:00Z",
    )
    assert ok is False  # exact dupe by hash


def test_get_all_prompts(db):
    db.insert_prompt("prompt 1", source="test", project="p", session_id="s1", timestamp="t")
    db.insert_prompt("prompt 2", source="test", project="p", session_id="s2", timestamp="t")
    prompts = db.get_all_prompts()
    assert len(prompts) == 2


def test_mark_session_processed(db):
    assert not db.is_session_processed("/path/to/session.jsonl")
    db.mark_session_processed("/path/to/session.jsonl", source="claude-code")
    assert db.is_session_processed("/path/to/session.jsonl")


def test_update_embedding(db):
    db.insert_prompt("test", source="test", project="p", session_id="s", timestamp="t")
    prompts = db.get_all_prompts()
    db.update_embedding(prompts[0]["id"], b"fake_embedding")
    updated = db.get_prompts_without_embedding()
    assert len(updated) == 0


def test_mark_duplicate(db):
    db.insert_prompt("original", source="test", project="p", session_id="s", timestamp="t")
    db.insert_prompt("near dupe", source="test", project="p", session_id="s", timestamp="t")
    all_p = db.get_all_prompts()
    db.mark_duplicate(all_p[1]["id"], all_p[0]["id"])
    updated = db.get_all_prompts()
    assert updated[1]["duplicate_of"] == all_p[0]["id"]


def test_prompt_patterns_crud(db):
    pattern_id = db.insert_pattern(
        pattern_text="fix the failing test",
        frequency=5,
        avg_length=25.0,
        projects=["proj1", "proj2"],
        category="debug",
        first_seen="2026-01-01",
        last_seen="2026-03-01",
        examples=[1, 2, 3],
    )
    assert pattern_id > 0
    patterns = db.get_patterns()
    assert len(patterns) == 1
    assert patterns[0]["category"] == "debug"


def test_term_stats_upsert(db):
    db.upsert_term_stats("python", count=10, df=5, tfidf_avg=0.42)
    db.upsert_term_stats("python", count=15, df=7, tfidf_avg=0.38)
    stats = db.get_term_stats()
    assert len(stats) == 1
    assert stats[0]["count"] == 15


def test_upsert_pattern_no_duplicates(db):
    """Running upsert_pattern twice with same text does not create a second row."""
    db.upsert_pattern(
        pattern_text="fix the failing test",
        frequency=3,
        avg_length=20.0,
        projects=[],
        category="debug",
        first_seen="2026-01-01",
        last_seen="2026-01-10",
        examples=["ex1"],
    )
    db.upsert_pattern(
        pattern_text="fix the failing test",
        frequency=7,
        avg_length=22.0,
        projects=[],
        category="debug",
        first_seen="2026-01-01",
        last_seen="2026-02-01",
        examples=["ex1", "ex2"],
    )
    patterns = db.get_patterns()
    assert len(patterns) == 1
    assert patterns[0]["frequency"] == 7
    assert patterns[0]["avg_length"] == 22.0


def test_upsert_pattern_id_stability(db):
    """The row ID must not change across multiple upserts of the same pattern."""
    first_id = db.upsert_pattern(
        pattern_text="implement feature X",
        frequency=2,
        avg_length=18.0,
        projects=[],
        category="feature",
        first_seen="2026-01-01",
        last_seen="2026-01-01",
        examples=[],
    )
    second_id = db.upsert_pattern(
        pattern_text="implement feature X",
        frequency=5,
        avg_length=19.5,
        projects=[],
        category="feature",
        first_seen="2026-01-01",
        last_seen="2026-03-01",
        examples=["ex"],
    )
    assert first_id == second_id


def test_upsert_pattern_frequency_updates(db):
    """Frequency and avg_length are correctly updated on subsequent upserts."""
    db.upsert_pattern(
        pattern_text="explain this code",
        frequency=1,
        avg_length=17.0,
        projects=[],
        category="explain",
        first_seen="2026-01-01",
        last_seen="2026-01-01",
        examples=["old example"],
    )
    db.upsert_pattern(
        pattern_text="explain this code",
        frequency=9,
        avg_length=21.0,
        projects=["proj-a"],
        category="explain",
        first_seen="2026-01-01",
        last_seen="2026-03-11",
        examples=["new example 1", "new example 2"],
    )
    patterns = db.get_patterns()
    assert len(patterns) == 1
    p = patterns[0]
    assert p["frequency"] == 9
    assert p["avg_length"] == 21.0
    assert p["last_seen"] == "2026-03-11"
    assert "new example 1" in p["examples"]
