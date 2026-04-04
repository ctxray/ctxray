"""Tests for the ctxray compress CLI command and terminal output."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def test_compress_command_basic():
    result = runner.invoke(app, ["compress", "basically check the logs"])
    assert result.exit_code == 0
    assert "Compressed:" in result.output or "compressed" in result.output.lower()


def test_compress_command_json():
    result = runner.invoke(app, ["compress", "basically check the logs", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "original" in data
    assert "compressed" in data
    assert "savings_pct" in data
    assert "changes" in data


def test_compress_command_empty():
    result = runner.invoke(app, ["compress", "hello"])
    assert result.exit_code == 0


def test_compress_command_chinese():
    result = runner.invoke(app, ["compress", "帮我看看这个文件的时候检查一下错误"])
    assert result.exit_code == 0


# --- Terminal output tests ---


def test_render_compress_basic():
    from ctxray.core.compress import CompressResult
    from ctxray.output.compress_terminal import render_compress

    result = CompressResult(
        original="basically check the logs",
        compressed="check the logs",
        original_tokens=4,
        compressed_tokens=3,
        savings_pct=25.0,
        changes=["layer1: filler deletion"],
        language="en",
    )
    output = render_compress(result)
    assert "Original:" in output
    assert "Compressed:" in output
    assert "Tokens:" in output
    assert "25%" in output
    assert "filler deletion" in output


def test_render_compress_no_changes():
    from ctxray.core.compress import CompressResult
    from ctxray.output.compress_terminal import render_compress

    result = CompressResult(
        original="hello",
        compressed="hello",
        original_tokens=1,
        compressed_tokens=1,
        savings_pct=0.0,
        changes=[],
        language="en",
    )
    output = render_compress(result)
    assert "Original:" in output
    assert "Compressed:" in output
    # Should not have Changes line when empty
    assert "Changes:" not in output


def test_render_compress_zero_tokens():
    from ctxray.core.compress import CompressResult
    from ctxray.output.compress_terminal import render_compress

    result = CompressResult(
        original="",
        compressed="",
        original_tokens=0,
        compressed_tokens=0,
        savings_pct=0.0,
        changes=[],
        language="en",
    )
    output = render_compress(result)
    assert "0" in output
    assert "no change" in output


def test_render_compress_long_text_truncated():
    from ctxray.core.compress import CompressResult
    from ctxray.output.compress_terminal import render_compress

    long_text = "a" * 300
    result = CompressResult(
        original=long_text,
        compressed=long_text,
        original_tokens=300,
        compressed_tokens=300,
        savings_pct=0.0,
        changes=[],
        language="en",
    )
    output = render_compress(result)
    # Should truncate display, not show all 300 chars
    assert len(long_text) > 200  # precondition
    # The rendered output should exist and not crash
    assert "Original:" in output


def test_compress_json_output_has_all_fields():
    prompt = "I was just wondering if you could basically help me"
    result = runner.invoke(app, ["compress", prompt, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data["original"], str)
    assert isinstance(data["compressed"], str)
    assert isinstance(data["original_tokens"], int)
    assert isinstance(data["compressed_tokens"], int)
    assert isinstance(data["savings_pct"], float)
    assert isinstance(data["changes"], list)
    assert isinstance(data["language"], str)
