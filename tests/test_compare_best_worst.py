"""Tests for compare --best-worst feature."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class TestGetBestWorstPrompts:
    """Tests for db.get_best_worst_prompts()."""

    def _make_db(self, tmp_path: Path):
        from reprompt.storage.db import PromptDB

        db = PromptDB(tmp_path / "test.db")
        return db

    def _seed_prompt(self, db, text: str, score: float, source: str = "claude-code"):
        """Insert a prompt and its feature score into the DB."""
        import hashlib

        prompt_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        conn = db._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO prompts"
                " (hash, text, source, session_id, timestamp, char_count)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    prompt_hash,
                    text,
                    source,
                    "test-session",
                    datetime.now(timezone.utc).isoformat(),
                    len(text),
                ),
            )
            features = {"word_count": len(text.split()), "task_type": "code_generation"}
            conn.execute(
                "INSERT OR REPLACE INTO prompt_features"
                " (prompt_hash, features_json, overall_score, task_type, computed_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    prompt_hash,
                    json.dumps(features),
                    score,
                    "code_generation",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_returns_none_when_no_scored_prompts(self, tmp_path: Path):
        db = self._make_db(tmp_path)
        result = db.get_best_worst_prompts()
        assert result is None

    def test_returns_none_when_fewer_than_two_qualifying(self, tmp_path: Path):
        db = self._make_db(tmp_path)
        self._seed_prompt(db, "refactor the authentication module to use JWT tokens", 85.0)
        result = db.get_best_worst_prompts()
        assert result is None

    def test_returns_best_and_worst(self, tmp_path: Path):
        db = self._make_db(tmp_path)
        self._seed_prompt(db, "fix the bug in the login handler code", 30.0)
        self._seed_prompt(
            db,
            "refactor authentication module to use JWT tokens properly",
            90.0,
        )
        self._seed_prompt(db, "add error handling to the payment processing service", 60.0)
        result = db.get_best_worst_prompts()
        assert result is not None
        best_text, worst_text = result
        assert "refactor" in best_text  # score 90
        assert "fix" in worst_text  # score 30

    def test_filters_short_prompts(self, tmp_path: Path):
        db = self._make_db(tmp_path)
        self._seed_prompt(db, "fix this", 20.0)  # too short (2 words)
        self._seed_prompt(db, "help me", 95.0)  # too short (2 words)
        self._seed_prompt(
            db,
            "refactor the authentication module to use JWT tokens",
            50.0,
        )
        result = db.get_best_worst_prompts()
        assert result is None  # only 1 qualifying prompt

    def test_source_filter(self, tmp_path: Path):
        db = self._make_db(tmp_path)
        self._seed_prompt(db, "fix the bug in the login handler code", 30.0, source="cursor")
        self._seed_prompt(
            db,
            "refactor authentication module to use JWT tokens properly",
            90.0,
            source="claude-code",
        )
        self._seed_prompt(
            db,
            "add error handling to the payment processing service",
            60.0,
            source="claude-code",
        )
        result = db.get_best_worst_prompts(source="claude-code")
        assert result is not None
        best_text, worst_text = result
        assert "refactor" in best_text  # 90, claude-code
        assert "add error" in worst_text  # 60, claude-code
