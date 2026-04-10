"""Unified prompt diagnostic — score + lint + rewrite in one pass.

Single-command quality check that runs all engines and returns a combined result.
Designed as the "one command" onboarding experience.

Threshold Intelligence (validated by E1 experiment, 2026-04-08):
  Prompt quality follows a STEP FUNCTION, not a linear curve.
  Below threshold (~43): 83% failure rate.
  Above threshold: 94% success rate.
  The threshold indicator helps users know if their prompt "will work."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ctxray.core.prompt_dna import PromptDNA

# Default quality threshold — experimentally validated (E1: gemma4:e4b, 30 prompts,
# pass_rate jumps from 0.17 to 0.94 at this score). Can be overridden via --threshold.
DEFAULT_THRESHOLD: int = 43


@dataclass
class CheckResult:
    """Combined result from all quality engines."""

    # Score
    total: float = 0.0
    tier: str = ""
    clarity: float = 0.0
    context: float = 0.0
    position: float = 0.0
    structure: float = 0.0
    repetition: float = 0.0

    # Threshold
    threshold: int = DEFAULT_THRESHOLD
    threshold_pass: bool = False  # True if total >= threshold
    missing_features: list[str] = field(default_factory=list)  # what to add to pass

    # Strengths
    confirmations: list[dict] = field(default_factory=list)

    # Suggestions with points
    suggestions: list[dict] = field(default_factory=list)

    # Lint violations
    lint_issues: list[dict] = field(default_factory=list)

    # Rewrite
    rewritten: str = ""
    rewrite_delta: float = 0.0
    rewrite_changes: list[str] = field(default_factory=list)

    # Meta
    word_count: int = 0
    token_count: int = 0


def _diagnose_missing_features(dna: PromptDNA) -> list[str]:
    """Identify concrete features that would push a prompt above threshold.

    Returns actionable suggestions ordered by expected point gain (highest first).
    """
    missing: list[tuple[int, str]] = []  # (points, message)
    if not dna.has_file_references and dna.task_type in ("debug", "implement", "refactor", "test"):
        missing.append((6, "Add file path references (e.g., src/auth.py)"))
    if not dna.has_error_messages and dna.task_type == "debug":
        missing.append((6, "Include the actual error message"))
    if not dna.has_code_blocks:
        missing.append((7, "Add relevant code snippets in ``` blocks"))
    if not dna.has_constraints:
        missing.append((5, "Add constraints (e.g., 'do not modify tests')"))
    if dna.word_count < 20:
        missing.append((6, "Add more context — describe what, where, and why"))
    if dna.ambiguity_score > 0.5:
        missing.append((4, "Replace vague words ('it', 'this') with specific names"))
    if not dna.has_io_spec:
        missing.append((3, "Specify expected input/output"))
    if not dna.has_edge_cases and dna.task_type in ("implement", "test"):
        missing.append((2, "Mention edge cases (empty input, null values)"))

    # Sort by points descending, return messages only
    missing.sort(key=lambda x: -x[0])
    return [msg for _, msg in missing]


def check_prompt(
    text: str,
    *,
    model: str = "",
    max_tokens: int = 0,
    threshold: int = DEFAULT_THRESHOLD,
) -> CheckResult:
    """Run all quality checks on a prompt in one pass."""
    from ctxray.core.extractors import extract_features
    from ctxray.core.lint import LintConfig, lint_prompt
    from ctxray.core.rewrite import rewrite_prompt
    from ctxray.core.scorer import get_tier, score_prompt

    # 1. Score
    dna = extract_features(text, source="check", session_id="")
    breakdown = score_prompt(dna, model=model)

    # 2. Threshold intelligence
    passes_threshold = breakdown.total >= threshold
    missing = _diagnose_missing_features(dna) if not passes_threshold else []

    # 3. Lint
    lint_config = LintConfig()
    if model and model in ("claude", "gpt", "gemini"):
        lint_config.model = model
    if max_tokens > 0:
        lint_config.max_tokens = max_tokens
    violations = lint_prompt(text, lint_config)

    # 4. Rewrite
    rewrite_result = rewrite_prompt(text)

    # Build result
    tier = get_tier(breakdown.total)

    return CheckResult(
        total=breakdown.total,
        tier=tier,
        threshold=threshold,
        threshold_pass=passes_threshold,
        missing_features=missing,
        clarity=breakdown.clarity,
        context=breakdown.context,
        position=breakdown.position,
        structure=breakdown.structure,
        repetition=breakdown.repetition,
        confirmations=[
            {"category": c.category, "message": c.message, "score": c.score}
            for c in breakdown.confirmations
        ],
        suggestions=[
            {
                "category": s.category,
                "message": s.message,
                "impact": s.impact,
                "points": s.points,
            }
            for s in breakdown.suggestions
        ],
        lint_issues=[
            {"rule": v.rule, "severity": v.severity, "message": v.message} for v in violations
        ],
        rewritten=rewrite_result.rewritten,
        rewrite_delta=rewrite_result.score_delta,
        rewrite_changes=rewrite_result.changes,
        word_count=dna.word_count,
        token_count=dna.token_count,
    )
