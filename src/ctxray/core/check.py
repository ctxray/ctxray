"""Unified prompt diagnostic — score + lint + rewrite in one pass.

Single-command quality check that runs all engines and returns a combined result.
Designed as the "one command" onboarding experience.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


def check_prompt(
    text: str,
    *,
    model: str = "",
    max_tokens: int = 0,
) -> CheckResult:
    """Run all quality checks on a prompt in one pass."""
    from ctxray.core.extractors import extract_features
    from ctxray.core.lint import LintConfig, lint_prompt
    from ctxray.core.rewrite import rewrite_prompt
    from ctxray.core.scorer import get_tier, score_prompt

    # 1. Score
    dna = extract_features(text, source="check", session_id="")
    breakdown = score_prompt(dna)

    # 2. Lint
    lint_config = LintConfig()
    if model and model in ("claude", "gpt", "gemini"):
        lint_config.model = model
    if max_tokens > 0:
        lint_config.max_tokens = max_tokens
    violations = lint_prompt(text, lint_config)

    # 3. Rewrite
    rewrite_result = rewrite_prompt(text)

    # Build result
    tier = get_tier(breakdown.total)

    return CheckResult(
        total=breakdown.total,
        tier=tier,
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
