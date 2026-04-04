"""Tests for --file input support across prompt commands."""

import json

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


def _write_prompt(tmp_path, content="Fix the auth bug in src/auth.ts"):
    f = tmp_path / "prompt.txt"
    f.write_text(content)
    return str(f)


class TestFileInputCheck:
    def test_check_from_file(self, tmp_path):
        path = _write_prompt(tmp_path)
        result = runner.invoke(app, ["check", "ignored", "--file", path])
        assert result.exit_code == 0
        assert "Clarity" in result.output

    def test_check_file_not_found(self, tmp_path):
        result = runner.invoke(app, ["check", "x", "--file", "/nonexistent/file.txt"])
        assert result.exit_code == 1

    def test_check_file_json(self, tmp_path):
        path = _write_prompt(tmp_path)
        result = runner.invoke(app, ["check", "x", "--file", path, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] > 0


class TestFileInputScore:
    def test_score_from_file(self, tmp_path):
        path = _write_prompt(tmp_path)
        result = runner.invoke(app, ["score", "ignored", "--file", path])
        assert result.exit_code == 0

    def test_score_file_json(self, tmp_path):
        path = _write_prompt(tmp_path)
        result = runner.invoke(app, ["score", "x", "--file", path, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total" in data


class TestFileInputExplain:
    def test_explain_from_file(self, tmp_path):
        path = _write_prompt(tmp_path)
        result = runner.invoke(app, ["explain", "x", "--file", path])
        assert result.exit_code == 0
        assert "Analysis" in result.output

    def test_explain_file_json(self, tmp_path):
        path = _write_prompt(tmp_path)
        result = runner.invoke(app, ["explain", "x", "--file", path, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data


class TestFileInputRewrite:
    def test_rewrite_from_file(self, tmp_path):
        path = _write_prompt(
            tmp_path, "I was wondering if you could maybe fix the authentication bug"
        )
        result = runner.invoke(app, ["rewrite", "x", "--file", path])
        assert result.exit_code == 0

    def test_rewrite_file_diff(self, tmp_path):
        path = _write_prompt(
            tmp_path, "I was wondering if you could maybe fix the authentication bug"
        )
        result = runner.invoke(app, ["rewrite", "x", "--file", path, "--diff"])
        assert result.exit_code == 0


class TestFileInputCompress:
    def test_compress_from_file(self, tmp_path):
        path = _write_prompt(tmp_path, "Can you please help me refactor this code to be better?")
        result = runner.invoke(app, ["compress", "x", "--file", path])
        assert result.exit_code == 0

    def test_compress_file_json(self, tmp_path):
        path = _write_prompt(tmp_path, "Please help me with the thing")
        result = runner.invoke(app, ["compress", "x", "--file", path, "--json"])
        assert result.exit_code == 0


class TestMultilineFile:
    def test_multiline_prompt(self, tmp_path):
        content = (
            "Fix the authentication middleware.\n\n"
            "Context: JWT tokens expire after 1 hour.\n"
            "Error: 401 on /api/users endpoint.\n\n"
            "Don't modify existing tests."
        )
        path = _write_prompt(tmp_path, content)
        result = runner.invoke(app, ["check", "x", "--file", path, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] > 0
        assert data["word_count"] > 10
