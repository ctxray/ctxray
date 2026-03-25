"""Tests for compare --best-worst feature."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner


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


runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestCompareBestWorstCLI:
    """CLI integration tests for compare --best-worst."""

    def _make_db_with_data(self, tmp_path: Path):
        db = TestGetBestWorstPrompts()._make_db(tmp_path)
        seed = TestGetBestWorstPrompts()._seed_prompt
        seed(db, "fix the bug in the login handler code", 30.0)
        seed(
            db,
            "refactor authentication module to use JWT tokens properly",
            90.0,
        )
        seed(
            db,
            "add error handling to the payment processing service",
            60.0,
        )
        return tmp_path / "test.db"

    def test_best_worst_flag(self, tmp_path: Path, monkeypatch):
        db_path = self._make_db_with_data(tmp_path)
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))
        from reprompt.cli import app

        result = runner.invoke(app, ["compare", "--best-worst"])
        assert result.exit_code == 0
        text = _strip_ansi(result.output)
        assert "Prompt Comparison" in text

    def test_best_worst_json(self, tmp_path: Path, monkeypatch):
        db_path = self._make_db_with_data(tmp_path)
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))
        from reprompt.cli import app

        result = runner.invoke(app, ["compare", "--best-worst", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "prompt_a" in data
        assert "prompt_b" in data

    def test_best_worst_shows_prompt_texts(self, tmp_path: Path, monkeypatch):
        db_path = self._make_db_with_data(tmp_path)
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))
        from reprompt.cli import app

        result = runner.invoke(app, ["compare", "--best-worst"])
        text = _strip_ansi(result.output)
        assert "Best:" in text or "refactor" in text.lower()

    def test_mutual_exclusion_error(self, tmp_path: Path, monkeypatch):
        db_path = self._make_db_with_data(tmp_path)
        monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))
        from reprompt.cli import app

        result = runner.invoke(app, ["compare", "prompt a", "prompt b", "--best-worst"])
        assert result.exit_code == 1

    def test_no_args_no_flag_error(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "empty.db"))
        from reprompt.cli import app

        result = runner.invoke(app, ["compare"])
        assert result.exit_code == 1

    def test_best_worst_empty_db(self, tmp_path: Path, monkeypatch):
        from reprompt.storage.db import PromptDB

        PromptDB(tmp_path / "empty.db")
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "empty.db"))
        from reprompt.cli import app

        result = runner.invoke(app, ["compare", "--best-worst"])
        text = _strip_ansi(result.output)
        assert "scan" in text.lower() or "score" in text.lower()

    def test_best_worst_with_source(self, tmp_path: Path, monkeypatch):
        db = TestGetBestWorstPrompts()._make_db(tmp_path)
        seed = TestGetBestWorstPrompts()._seed_prompt
        seed(
            db,
            "fix the bug in the login handler code",
            30.0,
            source="cursor",
        )
        seed(
            db,
            "refactor authentication module to use JWT tokens properly",
            90.0,
            source="claude-code",
        )
        seed(
            db,
            "add error handling to the payment processing service",
            60.0,
            source="claude-code",
        )
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        from reprompt.cli import app

        result = runner.invoke(
            app,
            ["compare", "--best-worst", "--source", "claude-code", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "prompt_a" in data and "prompt_b" in data
        assert isinstance(data["prompt_a"]["total"], (int, float))
        assert isinstance(data["prompt_b"]["total"], (int, float))
