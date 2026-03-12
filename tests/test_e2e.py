"""End-to-end test: fixture creation -> scan -> report -> library export."""

from __future__ import annotations

import json
from pathlib import Path

from reprompt.config import Settings
from reprompt.core.pipeline import build_report_data, run_scan
from reprompt.output.markdown import export_library_markdown
from reprompt.storage.db import PromptDB


def _create_claude_sessions(root: Path) -> None:
    """Create fake Claude Code session files."""
    project_dir = root / "-Users-testuser-projects-myapp"
    project_dir.mkdir(parents=True)

    # Session 1: debugging prompts
    session1 = project_dir / "session-001.jsonl"
    messages = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": (
                    "fix the failing test in the auth module, it's returning 401 instead of 200"
                ),
            },
            "timestamp": "2026-01-15T10:00:00Z",
        },
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": "Let me look at that..."},
            "timestamp": "2026-01-15T10:00:05Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": (
                    "fix the broken test in the payments module, similar issue with status codes"
                ),
            },
            "timestamp": "2026-01-15T10:05:00Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "fix the failing test in the users module, same 401 problem",
            },
            "timestamp": "2026-01-15T10:10:00Z",
        },
        {
            "type": "user",
            "message": {"role": "user", "content": "ok"},  # noise -- should be filtered
            "timestamp": "2026-01-15T10:15:00Z",
        },
    ]
    with open(session1, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    # Session 2: implementation prompts
    session2 = project_dir / "session-002.jsonl"
    messages2 = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "add a new REST endpoint for user profile management with GET and PUT",
            },
            "timestamp": "2026-02-01T10:00:00Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "implement the search feature with full-text search using SQLite FTS5",
            },
            "timestamp": "2026-02-01T10:30:00Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "add comprehensive unit tests for the new profile endpoint",
            },
            "timestamp": "2026-02-01T11:00:00Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "deploy the application to the staging environment for testing",
            },
            "timestamp": "2026-02-01T11:30:00Z",
        },
    ]
    with open(session2, "w") as f:
        for msg in messages2:
            f.write(json.dumps(msg) + "\n")

    # Session 3: more debug prompts (to create patterns with frequency >= 3)
    session3 = project_dir / "session-003.jsonl"
    messages3 = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "fix the test failure in the notification module, getting wrong status",
            },
            "timestamp": "2026-02-10T09:00:00Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "debug the authentication error when logging in with OAuth provider",
            },
            "timestamp": "2026-02-10T09:30:00Z",
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": (
                    "review this code for potential security vulnerabilities in the API layer"
                ),
            },
            "timestamp": "2026-02-10T10:00:00Z",
        },
    ]
    with open(session3, "w") as f:
        for msg in messages3:
            f.write(json.dumps(msg) + "\n")


def test_full_pipeline(tmp_path):
    """E2E: create fixtures -> scan -> verify DB -> report -> library export."""
    # 1. Create fake sessions
    sessions_root = tmp_path / "sessions"
    _create_claude_sessions(sessions_root)

    # 2. Configure
    db_path = tmp_path / "e2e_test.db"
    settings = Settings(db_path=db_path)

    # 3. Scan
    result = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
    assert result.sessions_scanned == 3
    assert result.total_parsed >= 9  # 10 user messages - 1 filtered "ok"
    assert result.unique_after_dedup > 0
    assert result.new_stored > 0

    # 4. Verify DB
    db = PromptDB(db_path)
    all_prompts = db.get_all_prompts()
    assert len(all_prompts) >= 7  # at least 7 unique prompts

    # 5. Build report
    report_data = build_report_data(settings=settings)
    assert report_data["overview"]["total_prompts"] > 0
    assert report_data["overview"]["unique_prompts"] > 0
    assert "claude-code" in report_data["overview"]["sources"]

    # 6. Export library
    patterns = db.get_patterns()
    md = export_library_markdown(patterns)
    md_path = tmp_path / "library.md"
    md_path.write_text(md)
    assert md_path.exists()
    assert len(md) > 50  # non-trivial output


def test_incremental_scan(tmp_path):
    """Verify second scan doesn't re-process sessions."""
    sessions_root = tmp_path / "sessions"
    _create_claude_sessions(sessions_root)
    db_path = tmp_path / "incr_test.db"
    settings = Settings(db_path=db_path)

    # First scan
    r1 = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
    assert r1.sessions_scanned == 3

    # Second scan -- should find nothing new
    r2 = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
    assert r2.sessions_scanned == 0
    assert r2.total_parsed == 0


def test_cli_scan_and_report(tmp_path, monkeypatch):
    """E2E via CLI: scan -> report -> library."""
    from typer.testing import CliRunner

    from reprompt.cli import app

    sessions_root = tmp_path / "sessions"
    _create_claude_sessions(sessions_root)
    db_path = tmp_path / "cli_test.db"
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    runner = CliRunner()

    # Scan
    result = runner.invoke(app, ["scan", "--source", "claude-code", "--path", str(sessions_root)])
    assert result.exit_code == 0
    assert "Scan complete" in result.output

    # Report
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0

    # JSON report
    result = runner.invoke(app, ["report", "--format", "json"])
    assert result.exit_code == 0

    # Status
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Total prompts" in result.output

    # Library
    result = runner.invoke(app, ["library"])
    assert result.exit_code == 0


def test_cli_library_export(tmp_path, monkeypatch):
    """E2E: CLI library export to Markdown file."""
    from typer.testing import CliRunner

    from reprompt.cli import app

    sessions_root = tmp_path / "sessions"
    _create_claude_sessions(sessions_root)
    db_path = tmp_path / "export_test.db"
    monkeypatch.setenv("REPROMPT_DB_PATH", str(db_path))

    runner = CliRunner()

    # Scan first
    runner.invoke(app, ["scan", "--source", "claude-code", "--path", str(sessions_root)])

    # Build report to populate patterns
    from reprompt.core.pipeline import build_report_data

    build_report_data(settings=Settings(db_path=db_path))

    # Export library
    export_path = str(tmp_path / "exported_library.md")
    result = runner.invoke(app, ["library", export_path])
    assert result.exit_code == 0
    assert Path(export_path).exists()
    content = Path(export_path).read_text()
    assert "Prompt Library" in content or "reprompt" in content


class TestScienceE2E:
    """End-to-end test for the Prompt Science Engine."""

    def test_score_compare_insights_flow(self, tmp_path):
        """Full flow: extract → score → store → insights."""
        from reprompt.core.extractors import extract_features
        from reprompt.core.insights import compute_insights
        from reprompt.core.scorer import score_prompt
        from reprompt.storage.db import PromptDB

        db = PromptDB(tmp_path / "test.db")

        prompts = [
            "Fix the TypeError in auth/login.py:42 when token.expiry is None",
            "Add tests for UserService — cover duplicate email and missing fields",
            "Fix bug",
            (
                "You are a senior engineer.\n\nRefactor PaymentService to strategy pattern."
                "\nDo not break existing tests.\nMust maintain backward compatibility."
            ),
        ]

        for text in prompts:
            dna = extract_features(text, source="test", session_id="e2e")
            breakdown = score_prompt(dna)
            dna.overall_score = breakdown.total
            db.store_features(dna.prompt_hash, dna.to_dict())

        # Verify features stored
        all_features = db.get_all_features()
        assert len(all_features) == 4

        # Verify scoring makes sense
        scores = sorted(all_features, key=lambda f: f["overall_score"])
        # "Fix bug" should score lowest
        assert scores[0]["word_count"] <= 5
        # The structured refactor prompt should score highest
        assert scores[-1]["has_constraints"] is True

        # Verify insights work
        result = compute_insights(all_features)
        assert result["prompt_count"] == 4
        assert result["avg_score"] > 0

    def test_score_cli_e2e(self):
        """CLI score command produces valid output."""
        from typer.testing import CliRunner

        from reprompt.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "score",
                "Fix the TypeError in auth/login.py:42. "
                "The validate_token function raises when token is None. "
                "Do not modify the test suite.",
            ],
        )
        assert result.exit_code == 0
        assert "Score" in result.output or "score" in result.output

    def test_compare_cli_e2e(self):
        """CLI compare command produces valid comparison."""
        from typer.testing import CliRunner

        from reprompt.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "compare",
                "Fix bug",
                "Fix the TypeError in auth/login.py:42 — validate_token raises on None input. "
                "Add a None guard before the expiry check. Do not modify tests.",
            ],
        )
        assert result.exit_code == 0
        assert "Prompt A" in result.output or "prompt_a" in result.output
