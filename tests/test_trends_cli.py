"""Tests for trends CLI command and terminal rendering."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.output.terminal import render_trends

runner = CliRunner()


def test_trends_command_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["trends"])
    assert result.exit_code == 0
    assert "Prompt Evolution" in result.output


def test_trends_command_json(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["trends", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "windows" in data
    assert "insights" in data


def test_trends_command_custom_period(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    result = runner.invoke(app, ["trends", "--period", "30d", "--windows", "2"])
    assert result.exit_code == 0


def test_trends_with_data(tmp_path, monkeypatch):
    monkeypatch.setenv("REPROMPT_DB_PATH", str(tmp_path / "test.db"))
    from datetime import datetime, timedelta, timezone

    from reprompt.storage.db import PromptDB

    db = PromptDB(tmp_path / "test.db")
    now = datetime.now(timezone.utc)
    for i in range(10):
        ts = (now - timedelta(days=i)).isoformat()
        db.insert_prompt(
            f"fix the authentication issue number {i} in the login module",
            source="cc",
            timestamp=ts,
        )

    result = runner.invoke(app, ["trends", "--period", "7d", "--windows", "2"])
    assert result.exit_code == 0
    assert "Prompts" in result.output


def test_render_trends_empty():
    data = {"period": "7d", "windows": [], "insights": []}
    output = render_trends(data)
    assert "No data" in output


def test_render_trends_with_windows():
    data = {
        "period": "7d",
        "windows": [
            {
                "window_label": "Mar 03 - Mar 10",
                "prompt_count": 42,
                "avg_length": 127.5,
                "vocab_size": 89,
                "specificity_score": 0.52,
            },
            {
                "window_label": "Mar 10 - Mar 17",
                "prompt_count": 51,
                "avg_length": 156.3,
                "vocab_size": 104,
                "specificity_score": 0.64,
                "specificity_pct": 23,
            },
        ],
        "insights": ["Your prompts are getting more specific (+23% over 2 periods)"],
    }
    output = render_trends(data)
    assert "Mar 03" in output
    assert "42" in output
    assert "51" in output
    assert "Insights" in output
    assert "more specific" in output


def test_render_trends_with_categories():
    data = {
        "period": "7d",
        "windows": [
            {
                "window_label": "Mar 10 - Mar 17",
                "prompt_count": 20,
                "avg_length": 100,
                "vocab_size": 50,
                "specificity_score": 0.5,
                "category_distribution": {"debug": 8, "implement": 12},
            },
        ],
        "insights": [],
    }
    output = render_trends(data)
    assert "Category Distribution" in output
    assert "debug" in output
    assert "implement" in output


def test_render_trends_delta_arrows():
    data = {
        "period": "7d",
        "windows": [
            {
                "window_label": "W1",
                "prompt_count": 10,
                "avg_length": 100,
                "vocab_size": 50,
                "specificity_score": 0.5,
            },
            {
                "window_label": "W2",
                "prompt_count": 15,
                "avg_length": 120,
                "vocab_size": 60,
                "specificity_score": 0.7,
                "specificity_pct": 40,
            },
        ],
        "insights": [],
    }
    output = render_trends(data)
    assert "+40%" in output
