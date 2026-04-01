"""Prompt quality linting rules.

Checks prompts against configurable quality rules and returns violations.
Designed for CI integration — each rule produces a severity + message.

Configuration loaded from (highest priority wins):
1. CLI flags (--score-threshold, --strict)
2. .reprompt.toml in CWD or parents
3. [tool.reprompt.lint] in pyproject.toml
4. Built-in defaults
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib  # type: ignore[no-redefine]


@dataclass
class LintViolation:
    """A single lint rule violation."""

    rule: str
    severity: str  # "error" | "warning"
    message: str
    prompt_text: str


@dataclass
class LintConfig:
    """Configuration for lint rules. Loaded from .reprompt.toml or pyproject.toml."""

    # Rule thresholds (0 = disabled)
    min_length: int = 20
    short_prompt: int = 40

    # Boolean rules (False = disabled)
    vague_prompt: bool = True
    debug_needs_reference: bool = True

    # File extensions for debug-needs-reference
    file_extensions: list[str] = field(
        default_factory=lambda: [".py", ".ts", ".js", ".go", ".rs", ".java", ".rb", ".cpp", ".c"]
    )

    # CI score threshold (0 = disabled, set via --score-threshold or config)
    score_threshold: int = 0


# --- Default config ---
DEFAULT_CONFIG = LintConfig()

VAGUE_STARTERS = frozenset(
    {"fix it", "fix this", "do it", "help me", "change it", "update it", "make it work"}
)


def load_lint_config(start_dir: Path | None = None) -> LintConfig:
    """Load lint config from .reprompt.toml or pyproject.toml, walking up from start_dir.

    Returns DEFAULT_CONFIG if no config file found.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    # Walk up to find config files
    current = start_dir.resolve()
    for _ in range(20):  # safety limit
        # Check .reprompt.toml first (project-specific)
        reprompt_toml = current / ".reprompt.toml"
        if reprompt_toml.is_file():
            return _parse_reprompt_toml(reprompt_toml)

        # Check pyproject.toml
        pyproject = current / "pyproject.toml"
        if pyproject.is_file():
            config = _parse_pyproject_toml(pyproject)
            if config is not None:
                return config

        parent = current.parent
        if parent == current:
            break
        current = parent

    return LintConfig()


def _parse_reprompt_toml(path: Path) -> LintConfig:
    """Parse a .reprompt.toml file."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return _build_config(data.get("lint", {}))
    except Exception:
        return LintConfig()


def _parse_pyproject_toml(path: Path) -> LintConfig | None:
    """Parse [tool.reprompt.lint] from pyproject.toml. Returns None if section missing."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        lint_section = data.get("tool", {}).get("reprompt", {}).get("lint")
        if lint_section is None:
            return None
        return _build_config(lint_section)
    except Exception:
        return None


def _build_config(lint_data: dict) -> LintConfig:
    """Build LintConfig from a parsed TOML dict."""
    config = LintConfig()

    # Top-level lint settings
    if "score-threshold" in lint_data:
        config.score_threshold = int(lint_data["score-threshold"])

    # Rule settings
    rules = lint_data.get("rules", {})

    # min-length: int threshold or false
    if "min-length" in rules:
        val = rules["min-length"]
        config.min_length = int(val) if val else 0

    # short-prompt: int threshold or false
    if "short-prompt" in rules:
        val = rules["short-prompt"]
        config.short_prompt = int(val) if val else 0

    # vague-prompt: bool
    if "vague-prompt" in rules:
        config.vague_prompt = bool(rules["vague-prompt"])

    # debug-needs-reference: bool
    if "debug-needs-reference" in rules:
        config.debug_needs_reference = bool(rules["debug-needs-reference"])

    # file-extensions: list
    if "file-extensions" in rules:
        config.file_extensions = list(rules["file-extensions"])

    return config


def lint_prompt(text: str, config: LintConfig | None = None) -> list[LintViolation]:
    """Lint a single prompt against quality rules."""
    if config is None:
        config = DEFAULT_CONFIG

    violations: list[LintViolation] = []
    stripped = text.strip().lower()

    # Rule 1: Too short
    if config.min_length > 0 and len(stripped) < config.min_length:
        violations.append(
            LintViolation(
                rule="min-length",
                severity="error",
                message=f"Prompt is too short ({len(stripped)} chars, minimum {config.min_length})",
                prompt_text=text,
            )
        )
    elif config.short_prompt > 0 and len(stripped) < config.short_prompt:
        violations.append(
            LintViolation(
                rule="short-prompt",
                severity="warning",
                message=(f"Prompt is short ({len(stripped)} chars) — consider adding context"),
                prompt_text=text,
            )
        )

    # Rule 2: Vague starter
    if config.vague_prompt and stripped in VAGUE_STARTERS:
        violations.append(
            LintViolation(
                rule="vague-prompt",
                severity="error",
                message="Prompt is too vague — specify what to fix/change and where",
                prompt_text=text,
            )
        )

    # Rule 3: No file/function reference in debug prompts
    if config.debug_needs_reference:
        debug_words = {"fix", "debug", "bug", "error", "broken", "failing", "crash"}
        has_debug_intent = any(w in stripped for w in debug_words)
        indicators = list(config.file_extensions) + ["()", "line ", "file "]
        has_reference = any(indicator in text for indicator in indicators)
        min_len = config.min_length if config.min_length > 0 else 20
        if has_debug_intent and not has_reference and len(stripped) >= min_len:
            violations.append(
                LintViolation(
                    rule="debug-needs-reference",
                    severity="warning",
                    message="Debug prompt lacks file/function reference — add specifics",
                    prompt_text=text,
                )
            )

    return violations


def lint_prompts(texts: list[str], config: LintConfig | None = None) -> list[LintViolation]:
    """Lint multiple prompts and return all violations."""
    violations: list[LintViolation] = []
    for text in texts:
        violations.extend(lint_prompt(text, config))
    return violations


def format_lint_results(violations: list[LintViolation], total_prompts: int) -> str:
    """Format lint results for terminal/CI output."""
    if not violations:
        return f"✓ {total_prompts} prompts checked, no issues found"

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    lines: list[str] = []
    lines.append(f"Checked {total_prompts} prompts\n")

    for v in violations:
        prefix = "✗" if v.severity == "error" else "!"
        display = v.prompt_text[:60] + "..." if len(v.prompt_text) > 60 else v.prompt_text
        lines.append(f'  {prefix} [{v.rule}] "{display}"')
        lines.append(f"    {v.message}")

    lines.append(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return "\n".join(lines)
