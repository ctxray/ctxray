"""Tests for ctxray lint CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def test_lint_no_prompts(tmp_path, monkeypatch):
    """Lint with no data should exit cleanly."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["lint", "--path", str(tmp_path / "nonexistent")])
    assert result.exit_code == 0
    assert "No prompts found" in result.output


def test_lint_clean_prompts(tmp_path, monkeypatch):
    """Good prompts should produce no errors."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "fix the authentication bug in auth.py — login returns 401",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-10",
    )
    db.insert_prompt(
        "add pagination to search results with cursor-based navigation",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-10",
    )

    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 0
    assert "no issues found" in result.output


def test_lint_bad_prompts_exit_1(tmp_path, monkeypatch):
    """Prompts with errors should exit 1."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("fix it", source="test", project="test", session_id="s1", timestamp="")

    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 1


def test_lint_json_output(tmp_path, monkeypatch):
    """JSON output should contain violations structure."""
    import json

    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("fix it", source="test", project="test", session_id="s1", timestamp="")

    result = runner.invoke(app, ["lint", "--json"])
    data = json.loads(result.output)
    assert data["total_prompts"] == 1
    assert data["errors"] >= 1
    assert len(data["violations"]) >= 1


def test_lint_strict_mode(tmp_path, monkeypatch):
    """Strict mode should exit 1 on warnings too."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    # A prompt that triggers warning but not error (short but above min)
    db.insert_prompt(
        "fix the auth bug please",
        source="test",
        project="test",
        session_id="s1",
        timestamp="",
    )

    result = runner.invoke(app, ["lint", "--strict"])
    assert result.exit_code == 1


def test_lint_score_threshold_pass(tmp_path, monkeypatch):
    """Score threshold with good prompts should pass."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "Fix the authentication bug in src/auth.py where JWT token validation "
        "fails with error: 'token expired' when refresh_token is still valid. "
        "The issue is in the verify_token() function around line 45.",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-28",
    )

    result = runner.invoke(app, ["lint", "--score-threshold", "10"])
    assert result.exit_code == 0
    assert "PASS" in result.output or "pass" in result.output.lower()


def test_lint_score_threshold_fail(tmp_path, monkeypatch):
    """Score threshold with vague prompts should fail."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "please help me with my code it is broken",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-28",
    )

    result = runner.invoke(app, ["lint", "--score-threshold", "90"])
    assert result.exit_code == 1
    assert "FAIL" in result.output or "fail" in result.output.lower()


def test_lint_score_threshold_json(tmp_path, monkeypatch):
    """Score threshold with JSON output should include score data."""
    import json

    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "Refactor the user authentication module in src/auth/ to use OAuth2 "
        "with PKCE flow instead of basic JWT. Keep backward compatibility.",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-28",
    )

    result = runner.invoke(app, ["lint", "--score-threshold", "10", "--json"])
    data = json.loads(result.output)
    assert "score" in data
    assert "avg_score" in data["score"]
    assert "threshold" in data["score"]
    assert data["score"]["pass"] is True


def test_lint_score_threshold_zero_is_noop(tmp_path, monkeypatch):
    """Score threshold of 0 (default) should not trigger scoring."""
    monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))

    from ctxray.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "fix the authentication bug in auth.py — login returns 401",
        source="test",
        project="test",
        session_id="s1",
        timestamp="2026-03-28",
    )

    result = runner.invoke(app, ["lint"])
    assert result.exit_code == 0
    # Score output should NOT appear when threshold is 0
    assert "threshold" not in result.output
