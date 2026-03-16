"""Tests for digest CLI command and render_digest()."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.output.terminal import render_digest, render_digest_history

runner = CliRunner()


class TestRenderDigest:
    def test_render_digest_empty_db(self):
        """render_digest() works with zero-prompt data."""
        data = {
            "period": "7d",
            "current": {
                "prompt_count": 0,
                "specificity_score": 0.0,
                "avg_length": 0.0,
                "category_distribution": {},
            },
            "previous": {
                "prompt_count": 0,
                "specificity_score": 0.0,
                "avg_length": 0.0,
                "category_distribution": {},
            },
            "count_delta": 0,
            "spec_delta": 0.0,
            "summary": "reprompt: 0 prompts (+0), specificity 0.00 (→)",
        }
        output = render_digest(data)
        assert "digest" in output.lower()
        assert "0" in output

    def test_render_digest_shows_prompt_count(self):
        data = {
            "period": "7d",
            "current": {
                "prompt_count": 42,
                "specificity_score": 0.72,
                "avg_length": 183.0,
                "category_distribution": {},
            },
            "previous": {
                "prompt_count": 37,
                "specificity_score": 0.65,
                "avg_length": 160.0,
                "category_distribution": {},
            },
            "count_delta": 5,
            "spec_delta": 0.07,
            "summary": "reprompt: 42 prompts (+5), specificity 0.72 (↑)",
        }
        output = render_digest(data)
        assert "42" in output
        assert "+5" in output

    def test_render_digest_shows_specificity_arrow_up(self):
        data = {
            "period": "7d",
            "current": {
                "prompt_count": 20,
                "specificity_score": 0.75,
                "avg_length": 150.0,
                "category_distribution": {},
            },
            "previous": {
                "prompt_count": 18,
                "specificity_score": 0.60,
                "avg_length": 130.0,
                "category_distribution": {},
            },
            "count_delta": 2,
            "spec_delta": 0.15,
            "summary": "reprompt: 20 prompts (+2), specificity 0.75 (↑)",
        }
        output = render_digest(data)
        assert "↑" in output

    def test_render_digest_shows_categories(self):
        data = {
            "period": "7d",
            "current": {
                "prompt_count": 30,
                "specificity_score": 0.65,
                "avg_length": 120.0,
                "category_distribution": {"implement": 18, "debug": 12},
            },
            "previous": {
                "prompt_count": 25,
                "specificity_score": 0.60,
                "avg_length": 110.0,
                "category_distribution": {"implement": 14, "debug": 11},
            },
            "count_delta": 5,
            "spec_delta": 0.05,
            "summary": "reprompt: 30 prompts (+5), specificity 0.65 (↑)",
        }
        output = render_digest(data)
        assert "implement" in output
        assert "debug" in output

    def test_render_digest_history_empty(self):
        output = render_digest_history([], "7d")
        assert "history" in output.lower()
        assert "No digest history" in output

    def test_render_digest_history_shows_rows(self):
        rows = [
            {
                "generated_at": "2026-03-10T08:00:00+00:00",
                "window_start": "2026-03-03T00:00:00+00:00",
                "window_end": "2026-03-10T00:00:00+00:00",
                "summary": "reprompt: 42 prompts (+5), specificity 0.62 (↑)",
            }
        ]
        output = render_digest_history(rows, "7d")
        assert "42 prompts" in output
        assert "2026-03-10" in output

    def test_render_digest_negative_delta(self):
        data = {
            "period": "7d",
            "current": {
                "prompt_count": 10,
                "specificity_score": 0.5,
                "avg_length": 100.0,
                "category_distribution": {},
            },
            "previous": {
                "prompt_count": 20,
                "specificity_score": 0.6,
                "avg_length": 120.0,
                "category_distribution": {},
            },
            "count_delta": -10,
            "spec_delta": -0.10,
            "summary": "reprompt: 10 prompts (-10), specificity 0.50 (↓)",
        }
        output = render_digest(data)
        assert "-10" in output
        assert "↓" in output


class TestDigestCommand:
    def test_digest_command_exits_cleanly(self, tmp_path, monkeypatch):
        """digest command exits 0 with empty DB."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest"])
        assert result.exit_code == 0

    def test_digest_command_quiet_mode(self, tmp_path, monkeypatch):
        """--quiet prints a single-line summary."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--quiet"])
        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().splitlines() if ln]
        assert len(lines) == 1
        assert "reprompt:" in lines[0]

    def test_digest_command_json(self, tmp_path, monkeypatch):
        """--format json returns valid JSON with expected keys."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Empty DB returns an error hint; non-empty returns digest keys
        if "error" in data:
            assert data["error"] == "no data"
            assert "reprompt scan" in data["hint"]
        else:
            assert "current" in data
            assert "previous" in data
            assert "count_delta" in data

    def test_digest_command_custom_period(self, tmp_path, monkeypatch):
        """digest accepts --period flag."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--period", "30d"])
        assert result.exit_code == 0

    def test_digest_shows_prompt_evolution_content(self, tmp_path, monkeypatch):
        """digest terminal output contains recognizable sections."""
        from datetime import datetime, timedelta, timezone

        from reprompt.storage.db import PromptDB

        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        db = PromptDB(tmp_path / "test.db")
        now = datetime.now(timezone.utc)
        for i in range(5):
            ts = (now - timedelta(days=i)).isoformat()
            db.insert_prompt(
                f"implement the user authentication flow {i} with JWT tokens",
                source="claude-code",
                timestamp=ts,
            )
        result = runner.invoke(app, ["digest"])
        assert result.exit_code == 0
        assert "digest" in result.output.lower()

    def test_digest_history_flag_empty(self, tmp_path, monkeypatch):
        """--history with empty DB prints a no-history message."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--history"])
        assert result.exit_code == 0
        assert "history" in result.output.lower()

    def test_digest_history_flag_json(self, tmp_path, monkeypatch):
        """--history --format json returns a JSON list."""
        monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--history", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_install_hook_with_digest_flag(self, tmp_path, monkeypatch):
        """--with-digest registers the digest --quiet entry in settings.json."""
        from pathlib import Path

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(app, ["install-hook", "--with-digest"])
        assert result.exit_code == 0
        data = json.loads((claude_dir / "settings.json").read_text())
        commands = [h.get("command") for h in data["hooks"]["Stop"] if isinstance(h, dict)]
        assert "reprompt digest --quiet" in commands

    def test_install_hook_with_digest_when_hook_already_exists(self, tmp_path, monkeypatch):
        """--with-digest still adds digest hook even when scan hook already installed."""
        from pathlib import Path

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # First install: scan hook only
        runner.invoke(app, ["install-hook"])
        # Second install: add digest hook to existing install
        result = runner.invoke(app, ["install-hook", "--with-digest"])
        assert result.exit_code == 0
        data = json.loads((claude_dir / "settings.json").read_text())
        commands = [h.get("command") for h in data["hooks"]["Stop"] if isinstance(h, dict)]
        assert "reprompt digest --quiet" in commands
