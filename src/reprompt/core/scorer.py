# src/reprompt/core/scorer.py
"""Weighted prompt scoring engine with research-calibrated weights.

Scores a PromptDNA feature vector on a 0-100 scale across five categories:
  1. Structure (0-25): role, constraints, examples, output format
  2. Context (0-25): code blocks, file refs, error messages, specificity
  3. Position (0-20): instruction placement (Lost in the Middle)
  4. Repetition (0-15): keyword reinforcement (Google Research)
  5. Clarity (0-15): low ambiguity, good opening, reasonable length

Each weight is derived from published research findings:
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


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown across categories."""

    total: float = 0.0

    # Category scores (each out of their max)
    structure: float = 0.0      # max 25
    context: float = 0.0        # max 25
    position: float = 0.0       # max 20
    repetition: float = 0.0     # max 15
    clarity: float = 0.0        # max 15

    suggestions: list[Suggestion] = field(default_factory=list)


def score_prompt(dna: PromptDNA) -> ScoreBreakdown:
    """Score a PromptDNA and return a detailed breakdown.

    Returns ScoreBreakdown with total in [0, 100] and per-category scores.
    """
    suggestions: list[Suggestion] = []

    # ── Structure (0-25) ──
    structure = 0.0
    if dna.has_role_definition:
        structure += 5.0
    else:
        suggestions.append(Suggestion(
            "structure", "Prompt Report",
            'Add a role definition (e.g., "You are a senior Python developer")',
            "medium",
        ))

    if dna.has_constraints:
        structure += 4.0 + min(dna.constraint_count, 3) * 1.0
    else:
        suggestions.append(Suggestion(
            "structure", "Prompt Report",
            'Add constraints (e.g., "Do not modify tests", "Must be backward-compatible")',
            "medium",
        ))

    if dna.has_examples:
        structure += 4.0 + min(dna.example_count, 2) * 1.0

    if dna.has_output_format:
        structure += 3.0

    if dna.has_step_by_step:
        structure += 2.0

    structure += min(dna.section_count, 3) * 1.0
    structure = min(structure, 25.0)

    # ── Context (0-25) ──
    context = 0.0
    if dna.has_code_blocks:
        context += 7.0
    if dna.has_file_references:
        context += 6.0
    else:
        if dna.task_type in ("debug", "implement", "refactor", "test"):
            suggestions.append(Suggestion(
                "context", "DETAIL arXiv:2512.02246",
                "Add file path references — specificity improves output quality significantly",
                "high",
            ))

    if dna.has_error_messages:
        context += 6.0
    elif dna.task_type == "debug":
        suggestions.append(Suggestion(
            "context", "DETAIL arXiv:2512.02246",
            "Include the actual error message — debug prompts with errors are 3.7x more effective",
            "high",
        ))

    context += 6.0 * min(dna.context_specificity, 1.0)
    context = min(context, 25.0)

    # ── Position (0-20) ──
    pos_score = _position_score(dna.key_instruction_position)
    position = 20.0 * pos_score

    if pos_score < 0.5 and dna.key_instruction_position > 0.3:
        suggestions.append(Suggestion(
            "position", "Lost in the Middle arXiv:2307.03172",
            "Your key instruction is buried in the middle — "
            "move it to the start or end for better attention (30% degradation in middle)",
            "high",
        ))

    # ── Repetition (0-15) ──
    rep = min(dna.keyword_repetition_freq, 1.0)
    repetition = 15.0 * rep

    if rep < 0.1 and dna.word_count > 20:
        suggestions.append(Suggestion(
            "repetition", "Google Research arXiv:2512.14982",
            "Repeating your core requirement at the end of the prompt "
            "can improve accuracy by up to 76%",
            "medium",
        ))

    # ── Clarity (0-15) ──
    clarity = 0.0

    # Opening quality
    clarity += 5.0 * min(dna.opening_quality, 1.0)

    # Low ambiguity
    clarity += 5.0 * max(0.0, 1.0 - dna.ambiguity_score)
    if dna.ambiguity_score > 0.5:
        suggestions.append(Suggestion(
            "clarity", "DETAIL arXiv:2512.02246",
            "Prompt is vague — replace pronouns ('it', 'this') with specific names",
            "high",
        ))

    # Reasonable length (not too short)
    if dna.word_count >= 20:
        clarity += 5.0
    elif dna.word_count >= 10:
        clarity += 3.0
    elif dna.word_count >= 5:
        clarity += 1.0
    else:
        suggestions.append(Suggestion(
            "clarity", "DETAIL arXiv:2512.02246",
            "Prompt is very short — add context about what, where, and why",
            "high",
        ))

    clarity = min(clarity, 15.0)

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
    )
