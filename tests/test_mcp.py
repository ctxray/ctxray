"""Tests for MCP server tools."""

from __future__ import annotations

import json

import pytest

from reprompt.storage.db import PromptDB


@pytest.fixture()
def mcp_db(tmp_path, monkeypatch):
    """Set up a test DB and point MCP tools at it."""
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    db = PromptDB(tmp_path / "test.db")
    db.insert_prompt(
        "fix the auth bug in the login handler",
        source="claude-code",
        timestamp="2026-03-10T10:00:00Z",
    )
    db.insert_prompt(
        "add unit tests for payment module", source="claude-code", timestamp="2026-03-10T11:00:00Z"
    )
    db.insert_prompt(
        "refactor the database connection pool",
        source="claude-code",
        timestamp="2026-03-10T12:00:00Z",
    )
    return db


def test_search_prompts_found(mcp_db):
    from reprompt.mcp import search_prompts

    result = search_prompts("auth")
    data = json.loads(result)
    assert len(data) == 1
    assert "auth" in data[0]["text"]


def test_search_prompts_not_found(mcp_db):
    from reprompt.mcp import search_prompts

    result = search_prompts("nonexistent_xyz")
    assert "No prompts" in result


def test_get_status(mcp_db):
    from reprompt.mcp import get_status

    result = json.loads(get_status())
    assert result["total_prompts"] == 3


def test_get_prompt_library_empty(mcp_db):
    from reprompt.mcp import get_prompt_library

    result = get_prompt_library()
    assert "No patterns" in result


def test_get_trends(mcp_db):
    from reprompt.mcp import get_trends

    result = json.loads(get_trends(period="7d", windows=2))
    assert "windows" in result
    assert len(result["windows"]) == 2


def test_get_best_prompts_empty(mcp_db):
    from reprompt.mcp import get_best_prompts

    result = get_best_prompts(category="debug")
    assert "No patterns" in result


def test_scan_sessions_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    from reprompt.mcp import scan_sessions

    result = json.loads(scan_sessions(source="claude-code"))
    # May find real sessions on dev machine; just verify structure
    assert "sessions_scanned" in result
    assert "new_stored" in result


def test_resource_status(mcp_db):
    from reprompt.mcp import resource_status

    result = json.loads(resource_status())
    assert "total_prompts" in result


def test_resource_library(mcp_db):
    from reprompt.mcp import resource_library

    result = json.loads(resource_library())
    assert isinstance(result, list)


def test_mcp_serve_cli(tmp_path, monkeypatch):
    """mcp-serve command exists and shows error without fastmcp if needed."""
    from typer.testing import CliRunner

    from reprompt.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["mcp-serve", "--help"])
    assert result.exit_code == 0
    assert "MCP" in result.output or "mcp" in result.output
