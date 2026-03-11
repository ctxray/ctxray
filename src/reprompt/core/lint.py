"""Prompt quality linting rules.

Checks prompts against configurable quality rules and returns violations.
Designed for CI integration — each rule produces a severity + message.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LintViolation:
    """A single lint rule violation."""

    rule: str
    severity: str  # "error" | "warning"
    message: str
    prompt_text: str


# --- Default thresholds ---
MIN_LENGTH = 20
SHORT_WARNING_LENGTH = 40
VAGUE_STARTERS = frozenset(
    {"fix it", "fix this", "do it", "help me", "change it", "update it", "make it work"}
)


def lint_prompt(text: str) -> list[LintViolation]:
    """Lint a single prompt against quality rules."""
    violations: list[LintViolation] = []
    stripped = text.strip().lower()

    # Rule 1: Too short
    if len(stripped) < MIN_LENGTH:
        violations.append(
            LintViolation(
                rule="min-length",
                severity="error",
                message=f"Prompt is too short ({len(stripped)} chars, minimum {MIN_LENGTH})",
                prompt_text=text,
            )
        )
    elif len(stripped) < SHORT_WARNING_LENGTH:
        violations.append(
            LintViolation(
                rule="short-prompt",
                severity="warning",
                message=f"Prompt is short ({len(stripped)} chars) — consider adding context",
                prompt_text=text,
            )
        )

    # Rule 2: Vague starter
    if stripped in VAGUE_STARTERS:
        violations.append(
            LintViolation(
                rule="vague-prompt",
                severity="error",
                message="Prompt is too vague — specify what to fix/change and where",
                prompt_text=text,
            )
        )

    # Rule 3: No file/function reference in debug prompts
    debug_words = {"fix", "debug", "bug", "error", "broken", "failing", "crash"}
    has_debug_intent = any(w in stripped for w in debug_words)
    has_reference = any(
        indicator in text
        for indicator in (".py", ".ts", ".js", ".go", ".rs", "()", "line ", "file ")
    )
    if has_debug_intent and not has_reference and len(stripped) >= MIN_LENGTH:
        violations.append(
            LintViolation(
                rule="debug-needs-reference",
                severity="warning",
                message="Debug prompt lacks file/function reference — add specifics",
                prompt_text=text,
            )
        )

    return violations


def lint_prompts(texts: list[str]) -> list[LintViolation]:
    """Lint multiple prompts and return all violations."""
    violations: list[LintViolation] = []
    for text in texts:
        violations.extend(lint_prompt(text))
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
