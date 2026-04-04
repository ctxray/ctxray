"""Tests for ctxray init command."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def test_init_creates_config(tmp_path: Path) -> None:
    os.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    config = tmp_path / ".ctxray.toml"
    assert config.exists()
    content = config.read_text()
    assert "[lint]" in content
    assert "[lint.rules]" in content
    assert "min-length" in content


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    os.chdir(tmp_path)
    (tmp_path / ".ctxray.toml").write_text("existing")
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "already exists" in result.output
    # Original content preserved
    assert (tmp_path / ".ctxray.toml").read_text() == "existing"


def test_init_force_overwrites(tmp_path: Path) -> None:
    os.chdir(tmp_path)
    (tmp_path / ".ctxray.toml").write_text("old content")
    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    content = (tmp_path / ".ctxray.toml").read_text()
    assert "[lint]" in content
    assert "old content" not in content


def test_init_config_is_valid_toml(tmp_path: Path) -> None:
    """Generated config should be parseable TOML."""
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redefine]

    os.chdir(tmp_path)
    runner.invoke(app, ["init"])
    with open(tmp_path / ".ctxray.toml", "rb") as f:
        data = tomllib.load(f)
    assert "lint" in data
    assert "rules" in data["lint"]
    assert data["lint"]["rules"]["min-length"] == 20
    assert data["lint"]["rules"]["vague-prompt"] is True


def test_init_config_works_with_lint(tmp_path: Path) -> None:
    """Generated config should be loadable by lint config loader."""
    os.chdir(tmp_path)
    runner.invoke(app, ["init"])

    from ctxray.core.lint import load_lint_config

    config = load_lint_config(start_dir=tmp_path)
    assert config.min_length == 20
    assert config.short_prompt == 40
    assert config.vague_prompt is True
    assert config.debug_needs_reference is True
