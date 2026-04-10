# src/ctxray/core/scorer.py
"""Weighted prompt scoring engine with research-calibrated weights.

Scores a PromptDNA feature vector on a 0-100 scale across five categories:
  1. Clarity (0-25): low ambiguity, good opening, reasonable length
  2. Context (0-25): code blocks, file refs, error messages, specificity
  3. Position (0-20): instruction placement (Lost in the Middle)
  4. Structure (0-15): role, constraints, examples, output format
  5. Repetition (0-15): keyword reinforcement (Google Research)

Model-specific scoring:
  When a target model is specified, adjustments are applied after base
  scoring. Research basis:
  - PromptBridge arXiv:2512.01420 (27-39% cross-model transfer loss)
  - CompactPrompt arXiv:2510.18043 (compression helps Claude, not GPT)
  - IFEval++ arXiv:2512.14754 (format sensitivity varies by model)

Research references:
- Position weights from the U-curve in arXiv:2307.03172 (30% degradation)
- Repetition weights from arXiv:2512.14982 (up to 76% improvement)
- Specificity weights from DETAIL arXiv:2512.02246
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ctxray.core.prompt_dna import PromptDNA

# ── Model-specific scoring profiles ──
# Adjustments applied AFTER base scoring. Positive = bonus, negative = penalty.
#
# Calibration history:
#   v1 (2026-04-08): Official model guides + published research
#   v2 (2026-04-09): Local experiments (E2: format, E3v4: position, E4.5: compression)
#   v3 (2026-04-09): Cross-validated on 4 models × PC GPU + literature review
#     - Format bonuses REMOVED: 96-call cross-validation + Delimiter Hypothesis
#     - compression_bonus reduced to +1.0 (CompactPrompt paper)
#     - Position weight 20/100 confirmed by E3v4 U-curve (37% middle loss)
#   v4 (2026-04-09): Model capacity matching (E8: 96 calls, 4 models)
#     - Over-complexity penalty for small models: maximal prompts drop 64% on 1.5B
#     - Threshold: complexity_score > 0.5 hurts <2B models
#     - Optimal complexity = "role + constraints" (not maximal)


@dataclass(frozen=True)
class ScoringProfile:
    """Model-specific scoring adjustments.

    Only adjustments with experimental or documented evidence are included.
    Format preferences (XML/Markdown) were removed in v3 — cross-validated
    on 4 models (96 calls) showing zero signal, consistent with published
    research (2411.10541, Systima.ai Delimiter Hypothesis).
    """

    name: str
    description: str = ""
    # Technique adjustments (documented by model providers)
    cot_penalty: float = 0.0  # penalty if "think step by step" (o-series official docs)
    compression_bonus: float = 0.0  # bonus if prompt is lean (CompactPrompt paper)
    # Length adjustments (documented by model providers)
    verbose_penalty_per_100w: float = 0.0  # penalty per 100 words over threshold
    verbose_threshold: int = 500  # word count above which verbose penalty kicks in
    # Complexity capacity (E8: 96 calls, 4 models on PC GPU)
    # Small models (<2B) drop 64% at high complexity. Threshold: complexity_score > 0.5.
    over_complexity_penalty: float = 0.0  # penalty when complexity exceeds model capacity
    complexity_threshold: float = 1.0  # complexity_score above which penalty applies


PROFILES: dict[str, ScoringProfile] = {
    "generic": ScoringProfile(name="generic"),
    "claude": ScoringProfile(
        name="claude",
        description="Anthropic Claude — compression helps (E7 k=3 + CompactPrompt)",
        # E7 k=1 showed "compression hurts" but k=3 stabilized to "compression HELPS"
        # (+0.26 normal, +0.37 safe). Consistent with CompactPrompt paper.
        # k=1 noise was caused by Haiku's high variance at capability boundary.
        compression_bonus=1.0,
    ),
    "gpt": ScoringProfile(
        name="gpt",
        description="OpenAI GPT — o-series penalized by explicit CoT (official docs)",
        cot_penalty=-3.0,
    ),
    "gemini": ScoringProfile(
        name="gemini",
        description="Google Gemini — loses focus on long prompts (official prompting guide)",
        verbose_penalty_per_100w=-1.0,
        verbose_threshold=300,
    ),
    "small": ScoringProfile(
        name="small",
        description="Small models (<3B) — over-complex prompts hurt (E8: 64% drop at maximal)",
        over_complexity_penalty=-5.0,  # E8: 0.78→0.28 at maximal on 1.5B
        complexity_threshold=0.5,  # E8: "role+constraints" optimal, beyond hurts
    ),
}

VALID_MODELS: frozenset[str] = frozenset(PROFILES.keys()) - {"generic"}


def _compute_model_adjustment(dna: PromptDNA, profile: ScoringProfile) -> float:
    """Compute model-specific score adjustment from profile rules."""
    adj = 0.0

    # CoT penalty (for reasoning models like o-series)
    if dna.has_step_by_step and profile.cot_penalty:
        adj += profile.cot_penalty

    # Compression bonus (only for models with paper evidence)
    if profile.compression_bonus and dna.compressibility < 0.15:
        adj += profile.compression_bonus

    # Verbose penalty
    if profile.verbose_penalty_per_100w and dna.word_count > profile.verbose_threshold:
        excess_hundreds = (dna.word_count - profile.verbose_threshold) / 100
        adj += profile.verbose_penalty_per_100w * excess_hundreds

    # Over-complexity penalty for small models (E8 validated)
    if profile.over_complexity_penalty and dna.complexity_score > profile.complexity_threshold:
        adj += profile.over_complexity_penalty

    return adj


# ── Position scoring calibrated to Lost in the Middle U-curve ──
# Position 0.0 (start) → ~75% accuracy → score 1.0
# Position 0.5 (middle) → ~45% accuracy → score 0.0
# Position 1.0 (end) → ~65% accuracy → score 0.67
#
# We model this as: score = 1.0 - 2.0 * min(pos, 1.0 - pos) * valley_depth
# where valley_depth makes the middle worse than the end.


def _position_score(pos: float) -> float:
    """Convert instruction position to a quality score [0.0, 1.0].

    Implements the asymmetric U-curve from Lost in the Middle:
    start=best, middle=worst, end=moderate.
    """
    # Piecewise linear approximation of the empirical U-curve
    if pos <= 0.2:
        return 1.0
    if pos <= 0.5:
        # Linear decay from 1.0 to 0.0
        return 1.0 - (pos - 0.2) / 0.3
    # Recovery from 0.0 to 0.67 (end is better than middle but worse than start)
    return (pos - 0.5) / 0.5 * 0.67


@dataclass
class Suggestion:
    """A research-backed improvement suggestion."""

    category: str  # "position", "repetition", "structure", "context", "clarity"
    paper: str  # short citation
    message: str
    impact: str  # "high", "medium", "low"
    points: int = 0  # expected score gain if applied


@dataclass
class Confirmation:
    """Positive feedback for a detected feature."""

    category: str
    message: str
    score: str  # e.g. "20/20"


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown across categories."""

    total: float = 0.0

    # Category scores (each out of their max)
    structure: float = 0.0  # max 15
    context: float = 0.0  # max 25
    position: float = 0.0  # max 20
    repetition: float = 0.0  # max 15
    clarity: float = 0.0  # max 25

    suggestions: list[Suggestion] = field(default_factory=list)
    confirmations: list[Confirmation] = field(default_factory=list)


def get_tier(score: float) -> str:
    """Map numeric score to tier label."""
    if score >= 85:
        return "EXPERT"
    if score >= 70:
        return "STRONG"
    if score >= 50:
        return "GOOD"
    if score >= 30:
        return "BASIC"
    return "DRAFT"


def tier_color(score: float) -> str:
    """Rich markup color for a score's tier."""
    if score >= 85:
        return "bold magenta"
    if score >= 70:
        return "bold green"
    if score >= 50:
        return "bold yellow"
    if score >= 30:
        return "yellow"
    return "dim"


def score_prompt(dna: PromptDNA, *, model: str = "") -> ScoreBreakdown:
    """Score a PromptDNA and return a detailed breakdown.

    Args:
        dna: Feature vector from extract_features()
        model: Target model for model-specific adjustments (claude/gpt/gemini).
               Empty string uses generic (universal) scoring.

    Returns ScoreBreakdown with total in [0, 100] and per-category scores.
    """
    suggestions: list[Suggestion] = []

    # ── Structure (0-15) ──
    structure = 0.0
    if dna.has_role_definition:
        structure += 3.0
    else:
        suggestions.append(
            Suggestion(
                "structure",
                "Prompt Report",
                'Add a role definition (e.g., "You are a senior Python developer")',
                "low",
                points=3,
            )
        )

    if dna.has_constraints:
        structure += 3.0 + min(dna.constraint_count, 2) * 1.0
    else:
        suggestions.append(
            Suggestion(
                "structure",
                "Prompt Report",
                'Add constraints (e.g., "Do not modify tests", "Must be backward-compatible")',
                "medium",
                points=5,
            )
        )

    if dna.has_examples:
        structure += 2.0 + min(dna.example_count, 1) * 1.0

    if dna.has_output_format:
        structure += 2.0

    if dna.has_step_by_step:
        structure += 1.0

    structure += min(dna.section_count, 2) * 1.0
    structure = min(structure, 15.0)

    # ── Context (0-25) ──
    context = 0.0
    if dna.has_code_blocks:
        context += 7.0
    if dna.has_file_references:
        context += 6.0
    else:
        if dna.task_type in ("debug", "implement", "refactor", "test"):
            suggestions.append(
                Suggestion(
                    "context",
                    "DETAIL arXiv:2512.02246",
                    "Add file path references — specificity improves output quality significantly",
                    "high",
                    points=6,
                )
            )

    if dna.has_error_messages:
        context += 6.0
    elif dna.task_type == "debug":
        suggestions.append(
            Suggestion(
                "context",
                "DETAIL arXiv:2512.02246",
                "Include the actual error message — debug prompts with errors are 3.7x more effective",  # noqa: E501
                "high",
                points=6,
            )
        )

    # [Zi+ 2508.03678] Specificity drivers from PartialOrderEval
    if dna.has_io_spec:
        context += 3.0
    if dna.has_edge_cases:
        context += 2.0
    elif dna.task_type in ("implement", "test"):
        suggestions.append(
            Suggestion(
                "context",
                "Zi+ arXiv:2508.03678",
                "Mention edge cases (empty input, null values) — key specificity driver",
                "medium",
                points=2,
            )
        )

    context += 6.0 * min(dna.context_specificity, 1.0)
    context = min(context, 25.0)

    # ── Position (0-20) ──
    pos_score = _position_score(dna.key_instruction_position)
    position = 20.0 * pos_score

    if pos_score < 0.5 and dna.key_instruction_position > 0.3:
        suggestions.append(
            Suggestion(
                "position",
                "Lost in the Middle arXiv:2307.03172",
                "Move your key instruction to the start or end (30% degradation in middle)",
                "high",
                points=10,
            )
        )

    # ── Repetition (0-15) ──
    rep = min(dna.keyword_repetition_freq, 1.0)
    repetition = 13.0 * rep
    if dna.instruction_repetition:
        repetition += 2.0
    repetition = min(repetition, 15.0)

    if rep < 0.1 and dna.word_count > 20:
        suggestions.append(
            Suggestion(
                "repetition",
                "Google Research arXiv:2512.14982",
                "Repeat your core requirement at the end — can improve accuracy up to 76%",
                "medium",
                points=8,
            )
        )

    # ── Clarity (0-25) ──
    clarity = 0.0

    # Opening quality
    clarity += 9.0 * min(dna.opening_quality, 1.0)

    # Low ambiguity
    clarity += 8.0 * max(0.0, 1.0 - dna.ambiguity_score)
    if dna.ambiguity_score > 0.5:
        suggestions.append(
            Suggestion(
                "clarity",
                "DETAIL arXiv:2512.02246",
                "Replace pronouns ('it', 'this') with specific names",
                "high",
                points=4,
            )
        )

    # Reasonable length (not too short)
    if dna.word_count >= 20:
        clarity += 8.0
    elif dna.word_count >= 10:
        clarity += 5.0
    elif dna.word_count >= 5:
        clarity += 2.0
    else:
        suggestions.append(
            Suggestion(
                "clarity",
                "DETAIL arXiv:2512.02246",
                "Add more context about what, where, and why",
                "high",
                points=6,
            )
        )

    clarity = min(clarity, 25.0)

    # ── Positive confirmations ──
    confirmations: list[Confirmation] = []
    if pos_score >= 0.8:
        confirmations.append(
            Confirmation(
                "position",
                "Key instruction at the start — optimal placement",
                f"{round(position)}/20",
            )
        )
    if dna.has_file_references:
        confirmations.append(
            Confirmation(
                "context",
                "File references detected — specificity matters",
                f"{round(min(context, 25))}/25",
            )
        )
    if dna.has_error_messages:
        confirmations.append(
            Confirmation(
                "context",
                "Error context included — 3.7x more effective",
                f"{round(min(context, 25))}/25",
            )
        )
    if dna.has_constraints:
        confirmations.append(
            Confirmation(
                "structure", "Constraints defined — clear boundaries set", f"{round(structure)}/15"
            )
        )
    if dna.opening_quality >= 0.4:
        confirmations.append(
            Confirmation(
                "clarity", "Strong opening — starts with clear intent", f"{round(clarity)}/25"
            )
        )

    # ── Total ──
    total = structure + context + position + repetition + clarity

    # ── Model-specific adjustment ──
    model_adjustment = 0.0
    if model:
        profile = PROFILES.get(model, PROFILES["generic"])
        model_adjustment = _compute_model_adjustment(dna, profile)
        total += model_adjustment

    total = round(min(max(total, 0.0), 100.0), 1)

    return ScoreBreakdown(
        total=total,
        structure=round(structure, 1),
        context=round(context, 1),
        position=round(position, 1),
        repetition=round(repetition, 1),
        clarity=round(clarity, 1),
        suggestions=suggestions,
        confirmations=confirmations,
    )
