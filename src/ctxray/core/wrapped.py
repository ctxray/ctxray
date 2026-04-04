"""Wrapped report builder — aggregates stats and classifies persona."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ctxray.core.persona import PERSONAS, Persona, classify_persona
from ctxray.storage.db import PromptDB


@dataclass
class WrappedReport:
    """All data needed to render a Wrapped-style report."""

    total_prompts: int = 0
    scored_prompts: int = 0
    avg_overall: float = 0.0
    top_score: float = 0.0
    top_task_type: str = "other"
    avg_scores: dict[str, float] = field(default_factory=dict)
    task_distribution: dict[str, int] = field(default_factory=dict)
    persona: Persona = field(default_factory=lambda: PERSONAS["explorer"])

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "total_prompts": self.total_prompts,
            "scored_prompts": self.scored_prompts,
            "avg_overall": self.avg_overall,
            "top_score": self.top_score,
            "top_task_type": self.top_task_type,
            "avg_scores": self.avg_scores,
            "task_distribution": self.task_distribution,
            "persona": {
                "name": self.persona.name,
                "emoji": self.persona.emoji,
                "description": self.persona.description,
                "traits": self.persona.traits,
            },
        }


def build_wrapped(db: PromptDB) -> WrappedReport:
    """Build a complete Wrapped report from the database.

    1. Fetch aggregate stats via ``db.get_wrapped_stats()``.
    2. Fetch task-type distribution via ``db.get_task_type_distribution()``.
    3. Classify persona from average scores (or default to *explorer*).
    """
    stats = db.get_wrapped_stats()
    task_dist = db.get_task_type_distribution()

    scored_prompts: int = stats["scored_prompts"]

    if scored_prompts > 0:
        persona = classify_persona(stats["avg_scores"])
    else:
        persona = PERSONAS["explorer"]

    return WrappedReport(
        total_prompts=stats["total_prompts"],
        scored_prompts=scored_prompts,
        avg_overall=stats["avg_overall"],
        top_score=stats["top_score"],
        top_task_type=stats["top_task_type"] or "other",
        avg_scores=stats["avg_scores"],
        task_distribution=task_dist,
        persona=persona,
    )
