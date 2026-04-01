"""Tests for prompt linting rules and configuration."""

from __future__ import annotations

from pathlib import Path

from reprompt.core.lint import (
    LintConfig,
    LintViolation,
    format_lint_results,
    lint_prompt,
    lint_prompts,
    load_lint_config,
)


class TestLintPrompt:
    def test_good_prompt_no_violations(self):
        violations = lint_prompt("fix the authentication bug in auth.py — login returns 401")
        assert violations == []

    def test_too_short_error(self):
        violations = lint_prompt("fix bug")
        assert len(violations) == 1
        assert violations[0].rule == "min-length"
        assert violations[0].severity == "error"

    def test_short_warning(self):
        violations = lint_prompt("fix the auth bug please")
        rules = [v.rule for v in violations]
        assert "short-prompt" in rules

    def test_vague_prompt_error(self):
        violations = lint_prompt("fix it")
        rules = [v.rule for v in violations]
        assert "vague-prompt" in rules

    def test_debug_without_reference(self):
        violations = lint_prompt("fix the authentication error in the login flow")
        rules = [v.rule for v in violations]
        assert "debug-needs-reference" in rules

    def test_debug_with_reference_ok(self):
        violations = lint_prompt("fix the authentication error in auth.py login flow")
        rules = [v.rule for v in violations]
        assert "debug-needs-reference" not in rules

    def test_non_debug_no_reference_warning(self):
        """Non-debug prompts don't need file references."""
        violations = lint_prompt("add pagination to the search results page")
        rules = [v.rule for v in violations]
        assert "debug-needs-reference" not in rules


class TestLintPrompts:
    def test_multiple_prompts(self):
        violations = lint_prompts(
            [
                "fix the authentication bug in auth.py — login returns 401",
                "fix it",
                "add pagination to search results with cursor-based navigation",
            ]
        )
        assert len(violations) >= 1  # "fix it" triggers violations

    def test_empty_list(self):
        assert lint_prompts([]) == []


class TestFormatResults:
    def test_no_violations(self):
        result = format_lint_results([], 10)
        assert "no issues found" in result
        assert "10" in result

    def test_with_violations(self):
        violations = lint_prompt("fix it")
        result = format_lint_results(violations, 5)
        assert "error" in result
        assert "fix it" in result

    def test_truncates_long_prompts(self):
        long_prompt = "x" * 100
        v = LintViolation(rule="test", severity="error", message="test", prompt_text=long_prompt)
        result = format_lint_results([v], 1)
        assert "..." in result


# -- LintConfig tests --


class TestLintConfig:
    def test_default_config(self):
        config = LintConfig()
        assert config.min_length == 20
        assert config.short_prompt == 40
        assert config.vague_prompt is True
        assert config.debug_needs_reference is True
        assert config.score_threshold == 0
        assert ".py" in config.file_extensions

    def test_custom_min_length(self):
        config = LintConfig(min_length=10)
        # "fix bug" is 7 chars — under 10
        violations = lint_prompt("fix bug", config=config)
        assert any(v.rule == "min-length" for v in violations)
        # "very short" is 10 chars — at threshold, should pass
        violations = lint_prompt("0123456789", config=config)
        assert not any(v.rule == "min-length" for v in violations)

    def test_disabled_min_length(self):
        config = LintConfig(min_length=0)
        violations = lint_prompt("hi", config=config)
        assert not any(v.rule == "min-length" for v in violations)

    def test_disabled_short_prompt(self):
        config = LintConfig(min_length=0, short_prompt=0)
        violations = lint_prompt("fix the auth bug please", config=config)
        assert not any(v.rule == "short-prompt" for v in violations)

    def test_disabled_vague_prompt(self):
        config = LintConfig(min_length=0, vague_prompt=False)
        violations = lint_prompt("fix it", config=config)
        assert not any(v.rule == "vague-prompt" for v in violations)

    def test_disabled_debug_needs_reference(self):
        config = LintConfig(debug_needs_reference=False)
        violations = lint_prompt("fix the authentication error in the login flow", config=config)
        assert not any(v.rule == "debug-needs-reference" for v in violations)

    def test_custom_file_extensions(self):
        config = LintConfig(file_extensions=[".py", ".ts"])
        # .go is not in extensions, so no reference detected
        violations = lint_prompt("fix the authentication error in auth.go flow", config=config)
        assert any(v.rule == "debug-needs-reference" for v in violations)
        # .py IS in extensions
        violations = lint_prompt("fix the authentication error in auth.py flow", config=config)
        assert not any(v.rule == "debug-needs-reference" for v in violations)

    def test_custom_short_threshold(self):
        config = LintConfig(short_prompt=60)
        violations = lint_prompt("add pagination to the search results page")
        rules_default = [v.rule for v in violations]
        assert "short-prompt" not in rules_default  # 42 chars, under 40 default = no warning

        violations = lint_prompt("add pagination to the search results page", config=config)
        rules_custom = [v.rule for v in violations]
        assert "short-prompt" in rules_custom  # 42 chars, under 60 threshold

    def test_lint_prompts_with_config(self):
        config = LintConfig(min_length=0, short_prompt=0, vague_prompt=False)
        violations = lint_prompts(["fix it", "hi", "ok"], config=config)
        # With all rules disabled, everything passes
        assert violations == []


# -- Config file loading tests --


class TestLoadLintConfig:
    def test_no_config_returns_defaults(self, tmp_path: Path):
        config = load_lint_config(start_dir=tmp_path)
        assert config.min_length == 20
        assert config.short_prompt == 40
        assert config.score_threshold == 0

    def test_reprompt_toml(self, tmp_path: Path):
        toml_file = tmp_path / ".reprompt.toml"
        toml_file.write_text(
            "[lint]\nscore-threshold = 60\n\n[lint.rules]\nmin-length = 10\nvague-prompt = false\n"
        )
        config = load_lint_config(start_dir=tmp_path)
        assert config.score_threshold == 60
        assert config.min_length == 10
        assert config.vague_prompt is False
        # Unset rules keep defaults
        assert config.short_prompt == 40
        assert config.debug_needs_reference is True

    def test_pyproject_toml(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.reprompt.lint]\n"
            "score-threshold = 45\n\n"
            "[tool.reprompt.lint.rules]\n"
            "short-prompt = 0\n"
            "debug-needs-reference = false\n"
        )
        config = load_lint_config(start_dir=tmp_path)
        assert config.score_threshold == 45
        assert config.short_prompt == 0
        assert config.debug_needs_reference is False

    def test_reprompt_toml_takes_precedence(self, tmp_path: Path):
        """When both exist, .reprompt.toml wins."""
        (tmp_path / ".reprompt.toml").write_text("[lint]\nscore-threshold = 70\n")
        (tmp_path / "pyproject.toml").write_text("[tool.reprompt.lint]\nscore-threshold = 30\n")
        config = load_lint_config(start_dir=tmp_path)
        assert config.score_threshold == 70

    def test_walks_up_directories(self, tmp_path: Path):
        """Config in parent dir should be found."""
        (tmp_path / ".reprompt.toml").write_text("[lint]\nscore-threshold = 55\n")
        subdir = tmp_path / "src" / "module"
        subdir.mkdir(parents=True)
        config = load_lint_config(start_dir=subdir)
        assert config.score_threshold == 55

    def test_pyproject_without_reprompt_section(self, tmp_path: Path):
        """pyproject.toml without [tool.reprompt] should return defaults."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        config = load_lint_config(start_dir=tmp_path)
        assert config.min_length == 20  # default

    def test_invalid_toml_returns_defaults(self, tmp_path: Path):
        (tmp_path / ".reprompt.toml").write_text("this is not valid toml {{{{")
        config = load_lint_config(start_dir=tmp_path)
        assert config.min_length == 20  # graceful fallback

    def test_file_extensions_config(self, tmp_path: Path):
        (tmp_path / ".reprompt.toml").write_text(
            '[lint.rules]\nfile-extensions = [".py", ".ts", ".vue"]\n'
        )
        config = load_lint_config(start_dir=tmp_path)
        assert config.file_extensions == [".py", ".ts", ".vue"]

    def test_disable_all_rules(self, tmp_path: Path):
        (tmp_path / ".reprompt.toml").write_text(
            "[lint.rules]\n"
            "min-length = 0\n"
            "short-prompt = 0\n"
            "vague-prompt = false\n"
            "debug-needs-reference = false\n"
        )
        config = load_lint_config(start_dir=tmp_path)
        violations = lint_prompts(["fix it", "hi", "ok"], config=config)
        assert violations == []
