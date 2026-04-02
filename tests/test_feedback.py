"""Tests for feedback hint and command tracking."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from reprompt.core.suggestions import (
    FEEDBACK_COMMANDS_THRESHOLD,
    FEEDBACK_URL,
    maybe_feedback_hint,
)


class TestFeedbackHint:
    def _make_db(self, settings: dict[str, str] | None = None) -> MagicMock:
        """Create a mock DB with get_setting/set_setting."""
        store: dict[str, str] = dict(settings) if settings else {}
        db = MagicMock()
        db.get_setting = MagicMock(side_effect=lambda k: store.get(k))

        def _set(k: str, v: str) -> None:
            store[k] = v

        db.set_setting = MagicMock(side_effect=_set)
        db._store = store  # expose for assertions
        return db

    def test_returns_none_when_not_tty(self):
        db = self._make_db()
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = False
            assert maybe_feedback_hint(db, "score") is None

    def test_returns_none_when_already_shown(self):
        db = self._make_db({"feedback_hint_shown": "1"})
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            assert maybe_feedback_hint(db, "score") is None

    def test_tracks_commands_used(self):
        db = self._make_db()
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            maybe_feedback_hint(db, "score")
            assert "score" in db._store.get("commands_used", "")

    def test_returns_none_below_threshold(self):
        db = self._make_db()
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            # Only 1 command used
            result = maybe_feedback_hint(db, "score")
            assert result is None

    def test_returns_hint_at_threshold(self):
        # Pre-populate with threshold - 1 commands
        cmds = ["score", "rewrite", "check", "patterns"]
        assert len(cmds) == FEEDBACK_COMMANDS_THRESHOLD - 1
        db = self._make_db({"commands_used": ",".join(cmds)})
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            result = maybe_feedback_hint(db, "insights")  # 5th unique command
            assert result is not None
            assert "feedback" in result

    def test_marks_shown_after_trigger(self):
        cmds = ["score", "rewrite", "check", "patterns"]
        db = self._make_db({"commands_used": ",".join(cmds)})
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            maybe_feedback_hint(db, "insights")
            assert db._store.get("feedback_hint_shown") == "1"

    def test_duplicate_commands_dont_count(self):
        db = self._make_db()
        with patch("reprompt.core.suggestions.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            result = None
            for _ in range(10):
                result = maybe_feedback_hint(db, "score")
            # Only 1 unique command, should not trigger
            assert result is None

    def test_feedback_url_is_valid(self):
        assert "github.com" in FEEDBACK_URL
        assert "feedback" in FEEDBACK_URL

    def test_threshold_is_reasonable(self):
        assert 3 <= FEEDBACK_COMMANDS_THRESHOLD <= 10
