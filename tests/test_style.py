"""Tests for personal prompting style analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from ctxray.core.style import compute_style


def test_compute_style_empty() -> None:
    result = compute_style([])
    assert result["prompt_count"] == 0
    assert result["avg_length"] == 0


def test_compute_style_basic() -> None:
    prompts = [
        {
            "text": "Add a login endpoint that returns JWT tokens",
            "category": "implement",
            "char_count": 46,
        },
        {"text": "Fix the auth bug in middleware", "category": "debug", "char_count": 30},
        {"text": "Add rate limiting to the API gateway", "category": "implement", "char_count": 36},
        {"text": "Explain how the cache layer works", "category": "explain", "char_count": 33},
        {
            "text": "Refactor the database module to use connection pooling",
            "category": "refactor",
            "char_count": 54,
        },
    ]
    result = compute_style(prompts)
    assert result["prompt_count"] == 5
    assert result["avg_length"] == pytest.approx(39.8, abs=0.1)
    assert result["top_category"] == "implement"
    assert result["top_category_pct"] == pytest.approx(0.4, abs=0.01)
    assert "category_distribution" in result
    assert "opening_patterns" in result
    assert "specificity" in result


def test_opening_patterns() -> None:
    prompts = [
        {"text": "Add a feature for user management", "category": "implement", "char_count": 34},
        {"text": "Add tests for the login flow", "category": "test", "char_count": 28},
        {"text": "Add documentation for the API", "category": "implement", "char_count": 29},
        {"text": "Fix the timeout error", "category": "debug", "char_count": 21},
        {"text": "Explain the deployment process", "category": "explain", "char_count": 30},
    ]
    result = compute_style(prompts)
    patterns = result["opening_patterns"]
    # "Add" should be the most common opener
    assert patterns[0]["word"] == "add"
    assert patterns[0]["count"] == 3


def test_specificity_score() -> None:
    # Specific prompts (mention files, functions, constraints)
    specific = [
        {
            "text": (
                "Fix the TypeError in auth/login.py:validate_token"
                " when token is expired and refresh fails"
            ),
            "category": "debug",
            "char_count": 90,
        },
        {
            "text": (
                "Add POST /api/users endpoint — accepts name+email, returns 201, 409 if duplicate"
            ),
            "category": "implement",
            "char_count": 82,
        },
    ]
    result = compute_style(specific)
    assert result["specificity"] > 0.5

    # Vague prompts
    vague = [
        {"text": "fix the bug", "category": "debug", "char_count": 11},
        {"text": "add a feature", "category": "implement", "char_count": 13},
    ]
    result_vague = compute_style(vague)
    assert result_vague["specificity"] < result["specificity"]


def test_category_distribution() -> None:
    prompts = [
        {"text": "Debug the auth", "category": "debug", "char_count": 14},
        {"text": "Debug the cache", "category": "debug", "char_count": 15},
        {"text": "Add tests", "category": "test", "char_count": 9},
    ]
    result = compute_style(prompts)
    dist = result["category_distribution"]
    assert dist["debug"] == 2
    assert dist["test"] == 1


def test_style_cli_json(tmp_path: Path) -> None:
    """CLI outputs valid JSON."""
    import json
    import os

    from typer.testing import CliRunner

    from ctxray.cli import app
    from ctxray.storage.db import PromptDB

    runner = CliRunner()
    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt("Fix the auth bug in login.py", source="test", project="p", session_id="s1")
    db.insert_prompt("Add unit tests for user service", source="test", project="p", session_id="s1")

    os.environ["CTXRAY_DB_PATH"] = str(tmp_path / "test.db")
    try:
        result = runner.invoke(app, ["style", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["prompt_count"] == 2
        assert "avg_length" in data
    finally:
        del os.environ["CTXRAY_DB_PATH"]


def test_style_cli_empty() -> None:
    """CLI handles empty database gracefully."""
    import os
    import tempfile

    from typer.testing import CliRunner

    from ctxray.cli import app

    runner = CliRunner()

    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        os.environ["CTXRAY_DB_PATH"] = f.name
        try:
            result = runner.invoke(app, ["style"])
            assert result.exit_code == 0
            assert "No prompts" in result.output
        finally:
            del os.environ["CTXRAY_DB_PATH"]
