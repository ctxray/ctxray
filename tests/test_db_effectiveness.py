"""Tests for DB effectiveness columns and methods."""

from __future__ import annotations

import pytest

from ctxray.storage.db import PromptDB


@pytest.fixture
def db(tmp_path):
    return PromptDB(tmp_path / "test.db")


class TestMigrateV08:
    def test_prompts_has_effectiveness_score_column(self, db):
        """_migrate_v08 adds effectiveness_score to prompts table."""
        import sqlite3

        conn = sqlite3.connect(str(db.path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(prompts)").fetchall()]
        conn.close()
        assert "effectiveness_score" in cols

    def test_prompt_patterns_has_effectiveness_avg_column(self, db):
        """_migrate_v08 adds effectiveness_avg to prompt_patterns table."""
        import sqlite3

        conn = sqlite3.connect(str(db.path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(prompt_patterns)").fetchall()]
        conn.close()
        assert "effectiveness_avg" in cols

    def test_prompt_patterns_has_effectiveness_sample_size_column(self, db):
        """_migrate_v08 adds effectiveness_sample_size to prompt_patterns table."""
        import sqlite3

        conn = sqlite3.connect(str(db.path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(prompt_patterns)").fetchall()]
        conn.close()
        assert "effectiveness_sample_size" in cols

    def test_migrate_idempotent(self, tmp_path):
        """Creating PromptDB twice doesn't raise (ALTER TABLE is safe on existing columns)."""
        db1 = PromptDB(tmp_path / "test.db")
        db2 = PromptDB(tmp_path / "test.db")  # should not raise
        assert db2.path == db1.path


class TestUpdatePromptEffectiveness:
    def test_sets_effectiveness_score_on_prompts(self, db):
        """update_prompt_effectiveness sets score on all prompts from a session."""
        db.insert_prompt("Fix the failing unit tests", source="claude-code", session_id="sess1")
        db.insert_prompt(
            "Add documentation for the new API", source="claude-code", session_id="sess1"
        )
        db.insert_prompt(
            "Unrelated prompt from another session", source="claude-code", session_id="sess2"
        )

        db.update_prompt_effectiveness("sess1", 0.85)

        all_prompts = db.get_all_prompts()
        sess1_prompts = [p for p in all_prompts if p["session_id"] == "sess1"]
        sess2_prompts = [p for p in all_prompts if p["session_id"] == "sess2"]

        assert all(p["effectiveness_score"] == pytest.approx(0.85) for p in sess1_prompts)
        assert all(p["effectiveness_score"] is None for p in sess2_prompts)

    def test_update_nonexistent_session_is_noop(self, db):
        """update_prompt_effectiveness on unknown session_id does nothing."""
        db.update_prompt_effectiveness("nonexistent", 0.5)  # should not raise
        assert db.get_all_prompts() == []


class TestComputePatternEffectiveness:
    def test_sets_effectiveness_avg_for_matching_patterns(self, db):
        """compute_pattern_effectiveness sets avg from prompts containing the pattern."""
        db.insert_prompt(
            "Fix the failing tests for the auth module", source="claude-code", session_id="s1"
        )
        db.insert_prompt(
            "Fix the failing tests for the DB layer", source="claude-code", session_id="s2"
        )
        db.update_prompt_effectiveness("s1", 0.80)
        db.update_prompt_effectiveness("s2", 0.60)

        db.upsert_pattern(
            pattern_text="Fix the failing tests",
            frequency=2,
            avg_length=50.0,
            projects=[],
            category="debug",
            first_seen="2026-03-10",
            last_seen="2026-03-10",
            examples=[],
        )

        db.compute_pattern_effectiveness()

        patterns = db.get_patterns()
        p = next(x for x in patterns if x["pattern_text"] == "Fix the failing tests")
        assert p["effectiveness_avg"] == pytest.approx(0.70, abs=0.01)
        assert p["effectiveness_sample_size"] == 2

    def test_pattern_with_percent_character(self, db):
        """Pattern containing '%' should match literally, not as LIKE wildcard."""
        db.insert_prompt("Set width to 100% of container", source="claude-code", session_id="s1")
        db.insert_prompt("Set width to full container", source="claude-code", session_id="s2")
        db.update_prompt_effectiveness("s1", 0.90)
        db.update_prompt_effectiveness("s2", 0.50)

        db.upsert_pattern(
            pattern_text="100%",
            frequency=1,
            avg_length=30.0,
            projects=[],
            category="code",
            first_seen="2026-03-10",
            last_seen="2026-03-10",
            examples=[],
        )

        db.compute_pattern_effectiveness()

        patterns = db.get_patterns()
        p = next(x for x in patterns if x["pattern_text"] == "100%")
        # Only s1 contains "100%", so avg should be 0.90, not average of both
        assert p["effectiveness_avg"] == pytest.approx(0.90, abs=0.01)
        assert p["effectiveness_sample_size"] == 1

    def test_pattern_with_underscore_character(self, db):
        """Pattern containing '_' should match literally, not as LIKE single-char wildcard."""
        db.insert_prompt("Fix __init__.py import order", source="claude-code", session_id="s1")
        db.insert_prompt("Fix aainita.py import order", source="claude-code", session_id="s2")
        db.update_prompt_effectiveness("s1", 0.80)
        db.update_prompt_effectiveness("s2", 0.40)

        db.upsert_pattern(
            pattern_text="__init__",
            frequency=1,
            avg_length=30.0,
            projects=[],
            category="code",
            first_seen="2026-03-10",
            last_seen="2026-03-10",
            examples=[],
        )

        db.compute_pattern_effectiveness()

        patterns = db.get_patterns()
        p = next(x for x in patterns if x["pattern_text"] == "__init__")
        # Only s1 contains "__init__", so avg should be 0.80
        assert p["effectiveness_avg"] == pytest.approx(0.80, abs=0.01)
        assert p["effectiveness_sample_size"] == 1

    def test_pattern_with_very_long_text(self, db):
        """Pattern with 500+ chars should not crash the INSTR query."""
        long_pattern = "refactor " * 60  # 540 chars
        prompt_text = f"Please {long_pattern}the entire codebase"
        db.insert_prompt(prompt_text, source="claude-code", session_id="s1")
        db.update_prompt_effectiveness("s1", 0.75)

        db.upsert_pattern(
            pattern_text=long_pattern,
            frequency=1,
            avg_length=float(len(long_pattern)),
            projects=[],
            category="refactor",
            first_seen="2026-03-10",
            last_seen="2026-03-10",
            examples=[],
        )

        db.compute_pattern_effectiveness()

        patterns = db.get_patterns()
        p = next(x for x in patterns if x["pattern_text"] == long_pattern)
        assert p["effectiveness_avg"] == pytest.approx(0.75, abs=0.01)
        assert p["effectiveness_sample_size"] == 1

    def test_no_data_leaves_pattern_null(self, db):
        """Patterns with no linked effective prompts remain NULL."""
        db.upsert_pattern(
            pattern_text="Refactor the module",
            frequency=1,
            avg_length=30.0,
            projects=[],
            category="refactor",
            first_seen="2026-03-10",
            last_seen="2026-03-10",
            examples=[],
        )
        db.compute_pattern_effectiveness()
        patterns = db.get_patterns()
        p = next(x for x in patterns if x["pattern_text"] == "Refactor the module")
        assert p["effectiveness_avg"] is None
