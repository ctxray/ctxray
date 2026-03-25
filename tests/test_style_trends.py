"""Tests for style --trends feature."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reprompt.storage.db import PromptDB


class TestComputeStyleTrends:
    """Tests for compute_style_trends()."""

    def _make_db(self, tmp_path: Path):
        return PromptDB(tmp_path / "test.db")

    def _seed_prompts_in_window(
        self,
        db,
        texts: list[str],
        timestamp: datetime,
        source: str = "claude-code",
    ):
        """Insert prompts with a specific timestamp."""
        conn = db._conn()
        try:
            for text in texts:
                prompt_hash = hashlib.sha256((text + timestamp.isoformat()).encode()).hexdigest()[
                    :16
                ]
                conn.execute(
                    "INSERT OR IGNORE INTO prompts"
                    " (hash, text, source, session_id, timestamp, char_count)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        prompt_hash,
                        text,
                        source,
                        "test-session",
                        timestamp.isoformat(),
                        len(text),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def test_returns_empty_when_no_data(self, tmp_path: Path):
        from reprompt.core.style import compute_style_trends

        db = self._make_db(tmp_path)
        result = compute_style_trends(db, period="7d")
        assert result["current"]["prompt_count"] == 0
        assert result["previous"]["prompt_count"] == 0

    def test_computes_deltas(self, tmp_path: Path):
        from reprompt.core.style import compute_style_trends

        db = self._make_db(tmp_path)
        now = datetime.now(timezone.utc)

        # Previous window prompts (short, less specific)
        prev_time = now - timedelta(days=10)
        self._seed_prompts_in_window(
            db,
            [
                "fix this bug",
                "help me",
                "add a test",
                "update docs",
                "clean up code",
            ],
            prev_time,
        )

        # Current window prompts (longer, more specific)
        curr_time = now - timedelta(hours=1)
        self._seed_prompts_in_window(
            db,
            [
                "refactor the authentication module to use JWT tokens with proper expiry",
                "add error handling to src/api/handlers.py for the /users endpoint",
                "fix the TypeError in utils.parse_config() when config file is missing",
                "implement rate limiting middleware with a sliding window algorithm",
                "write integration tests for the payment processing pipeline",
            ],
            curr_time,
        )

        result = compute_style_trends(db, period="7d")
        assert result["period"] == "7d"
        assert result["current"]["prompt_count"] == 5
        assert result["previous"]["prompt_count"] == 5
        assert "deltas" in result
        assert "specificity" in result["deltas"]
        assert "avg_length" in result["deltas"]
        assert "prompt_count" in result["deltas"]

    def test_source_filter(self, tmp_path: Path):
        from reprompt.core.style import compute_style_trends

        db = self._make_db(tmp_path)
        now = datetime.now(timezone.utc)
        curr_time = now - timedelta(hours=1)

        self._seed_prompts_in_window(
            db,
            ["refactor the authentication module to use JWT tokens properly"],
            curr_time,
            source="claude-code",
        )
        self._seed_prompts_in_window(
            db,
            ["fix the bug in the login handler for edge cases"],
            curr_time,
            source="cursor",
        )

        result = compute_style_trends(db, period="7d", source="claude-code")
        assert result["current"]["prompt_count"] == 1

    def test_top_category_changed_flag(self, tmp_path: Path):
        from reprompt.core.style import compute_style_trends

        db = self._make_db(tmp_path)
        now = datetime.now(timezone.utc)

        # Previous: mostly explain prompts
        prev_time = now - timedelta(days=10)
        self._seed_prompts_in_window(
            db,
            [
                "explain how authentication works in this codebase",
                "explain the database schema and relationships",
                "explain the API routing pattern used here",
            ],
            prev_time,
        )

        # Current: mostly debugging prompts
        curr_time = now - timedelta(hours=1)
        self._seed_prompts_in_window(
            db,
            [
                "fix the TypeError in utils.parse_config() when config is None",
                "debug the failing test in test_auth.py line 42",
                "fix the race condition in the background worker queue",
            ],
            curr_time,
        )

        result = compute_style_trends(db, period="7d")
        assert "top_category_changed" in result["deltas"]
        assert "top_category_current" in result["deltas"]
        assert "top_category_previous" in result["deltas"]
