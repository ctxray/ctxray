"""Tests for ctxray demo command."""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from ctxray.cli import app
from ctxray.demo import generate_demo_sessions

runner = CliRunner()


class TestGenerateDemoSessions:
    def test_creates_session_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            n = generate_demo_sessions(Path(tmp) / "sessions", n_weeks=2)
            assert n > 0
            jsonl_files = list((Path(tmp) / "sessions").rglob("*.jsonl"))
            assert len(jsonl_files) > 0

    def test_creates_project_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generate_demo_sessions(Path(tmp) / "sessions", n_weeks=1)
            dirs = [d.name for d in (Path(tmp) / "sessions").iterdir() if d.is_dir()]
            assert len(dirs) > 0

    def test_returns_prompt_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            n = generate_demo_sessions(Path(tmp) / "sessions", n_weeks=1)
            assert isinstance(n, int)
            assert n >= 10


class TestDemoCommand:
    def test_demo_runs_successfully(self) -> None:
        result = runner.invoke(app, ["demo"])
        assert result.exit_code == 0
        assert "Generating demo data" in result.output
        assert "Scan complete" in result.output

    def test_demo_shows_report(self) -> None:
        result = runner.invoke(app, ["demo"])
        assert result.exit_code == 0
        assert "Hot Phrases" in result.output or "Overview" in result.output
