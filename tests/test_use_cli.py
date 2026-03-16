"""Tests for reprompt use CLI command."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from reprompt.cli import app
from reprompt.core.templates import save_template
from reprompt.storage.db import PromptDB

runner = CliRunner()


def _setup_db_with_template(tmp_path: Path) -> tuple[PromptDB, str]:
    """Create a DB with one template and return (db, db_path_str)."""
    db_path = tmp_path / "test.db"
    db = PromptDB(db_path)
    save_template(db, text="Fix {error_type} in {file_path}", name="fix-template", category="debug")
    return db, str(db_path)


def test_use_basic(tmp_path: Path) -> None:
    db, db_path = _setup_db_with_template(tmp_path)
    os.environ["REPROMPT_DB_PATH"] = db_path
    try:
        result = runner.invoke(
            app, ["use", "fix-template", "error_type=TypeError", "file_path=auth.py"]
        )
        assert result.exit_code == 0
        assert "Fix TypeError in auth.py" in result.output
    finally:
        del os.environ["REPROMPT_DB_PATH"]


def test_use_template_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    PromptDB(db_path)  # create empty DB
    os.environ["REPROMPT_DB_PATH"] = str(db_path)
    try:
        result = runner.invoke(app, ["use", "nonexistent"])
        assert result.exit_code != 0 or "not found" in result.output.lower()
    finally:
        del os.environ["REPROMPT_DB_PATH"]


def test_use_no_variables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    db = PromptDB(db_path)
    save_template(db, text="Run all tests", name="run-tests", category="run")
    os.environ["REPROMPT_DB_PATH"] = str(db_path)
    try:
        result = runner.invoke(app, ["use", "run-tests"])
        assert result.exit_code == 0
        assert "Run all tests" in result.output
    finally:
        del os.environ["REPROMPT_DB_PATH"]


def test_use_shows_variables_hint(tmp_path: Path) -> None:
    """When variables are needed but not provided, show which ones."""
    db, db_path = _setup_db_with_template(tmp_path)
    os.environ["REPROMPT_DB_PATH"] = db_path
    try:
        result = runner.invoke(app, ["use", "fix-template"])
        assert result.exit_code == 0
        # Should still output the template but with placeholders visible
        assert "{error_type}" in result.output or "error_type" in result.output
    finally:
        del os.environ["REPROMPT_DB_PATH"]


def test_use_increments_usage_count(tmp_path: Path) -> None:
    db, db_path = _setup_db_with_template(tmp_path)
    os.environ["REPROMPT_DB_PATH"] = db_path
    try:
        runner.invoke(app, ["use", "fix-template", "error_type=Bug", "file_path=x.py"])
        t = db.get_template("fix-template")
        assert t is not None
        assert t["usage_count"] == 1
    finally:
        del os.environ["REPROMPT_DB_PATH"]
