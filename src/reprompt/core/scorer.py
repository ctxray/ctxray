# src/reprompt/core/scorer.py
"""Weighted prompt scoring engine with research-calibrated weights.

Scores a PromptDNA feature vector on a 0-100 scale across five categories:
  1. Clarity (0-25): low ambiguity, good opening, reasonable length
  2. Context (0-25): code blocks, file refs, error messages, specificity
  3. Position (0-20): instruction placement (Lost in the Middle)
  4. Structure (0-15): role, constraints, examples, output format
  5. Repetition (0-15): keyword reinforcement (Google Research)

Weight rationale: clarity and context are what normal developers can
improve immediately; structure and repetition are advanced techniques
that provide additional lift. This ensures a clear, specific prompt
scores 55-65 without requiring markdown or role definitions.

Research references:
- Position weights from the U-curve in arXiv:2307.03172 (30% degradation)
- Repetition weights from arXiv:2512.14982 (up to 76% improvement)
- Specificity weights from DETAIL arXiv:2512.02246
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reprompt.core.prompt_dna import PromptDNA

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


def score_prompt(dna: PromptDNA) -> ScoreBreakdown:
    """Score a PromptDNA and return a detailed breakdown.

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
    total = round(min(total, 100.0), 1)

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
