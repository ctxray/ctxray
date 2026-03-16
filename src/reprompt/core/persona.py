"""Persona data model and centroids for prompt style classification.

Each persona represents a distinct prompting style, identified by a centroid
in 5-dimensional feature space:
  [structure_pct, context_pct, position_pct, repetition_pct, clarity_pct]
"""

from __future__ import annotations

import math  # noqa: F401 — re-exported for Task 2 (distance calculations)
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    """A prompt-writing persona with a centroid in feature space."""

    name: str
    emoji: str
    description: str
    traits: list[str]
    centroid: list[float]


_CATEGORY_MAX = {
    "structure": 25.0,
    "context": 25.0,
    "position": 20.0,
    "repetition": 15.0,
    "clarity": 15.0,
}

# Dimension order must match centroid vectors.
_DIM_ORDER = ["structure", "context", "position", "repetition", "clarity"]


def classify_persona(scores: dict[str, float]) -> Persona:
    """Classify a user's prompt persona based on average score breakdown.

    Parameters:
        scores: dict with keys *structure, context, position, repetition, clarity*.
            Values are raw scores (structure out of 25, context out of 25,
            position out of 20, repetition out of 15, clarity out of 15).

    Returns:
        The closest matching :class:`Persona` via Euclidean distance on
        normalized centroids.
    """
    # 1. Normalize scores to [0, 1]
    normalized = [scores[dim] / _CATEGORY_MAX[dim] for dim in _DIM_ORDER]

    # 2. Find persona with smallest Euclidean distance
    best_persona: Persona | None = None
    best_dist = float("inf")
    for persona in PERSONAS.values():
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(normalized, persona.centroid)))
        if dist < best_dist:
            best_dist = dist
            best_persona = persona

    assert best_persona is not None  # PERSONAS is non-empty
    return best_persona


PERSONAS: dict[str, Persona] = {
    "architect": Persona(
        name="architect",
        emoji="\U0001f9ec",
        description=(
            "You write prompts like a software architect \u2014 structured, constrained, precise."
        ),
        traits=[
            "Always defines constraints",
            "Uses structured sections",
            "Provides output format",
            "References specific files",
        ],
        centroid=[0.85, 0.70, 0.75, 0.50, 0.70],
    ),
    "debugger": Persona(
        name="debugger",
        emoji="\U0001f41b",
        description=(
            "You bring full context to every problem \u2014 errors, files, and stack traces."
        ),
        traits=[
            "Includes error messages",
            "References file paths",
            "Provides code blocks",
            "High context specificity",
        ],
        centroid=[0.50, 0.95, 0.60, 0.40, 0.55],
    ),
    "explorer": Persona(
        name="explorer",
        emoji="\U0001f50d",
        description=("You ask short, curious questions \u2014 exploring before committing."),
        traits=[
            "Short prompts",
            "Open-ended questions",
            "Low structure",
            "High variety",
        ],
        centroid=[0.20, 0.25, 0.60, 0.15, 0.40],
    ),
    "novelist": Persona(
        name="novelist",
        emoji="\U0001f4dd",
        description=(
            "You write detailed, thorough prompts with full context and step-by-step guidance."
        ),
        traits=[
            "Long, detailed prompts",
            "Role definitions",
            "Step-by-step instructions",
            "Multiple examples",
        ],
        centroid=[0.80, 0.60, 0.70, 0.65, 0.60],
    ),
    "sniper": Persona(
        name="sniper",
        emoji="\U0001f3af",
        description="You say exactly what you need in as few words as possible.",
        traits=[
            "Very concise",
            "High specificity",
            "Low ambiguity",
            "Direct instructions",
        ],
        centroid=[0.40, 0.50, 0.85, 0.30, 0.90],
    ),
    "teacher": Persona(
        name="teacher",
        emoji="\U0001f4da",
        description=("You guide AI with examples, step-by-step, and clear output expectations."),
        traits=[
            "Provides examples",
            "Step-by-step instructions",
            "Output format specified",
            "Patient, iterative approach",
        ],
        centroid=[0.90, 0.55, 0.65, 0.70, 0.65],
    ),
}
