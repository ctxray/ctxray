"""Personal prompt patterns — analyze recurring weaknesses in prompt history.

Reads PromptDNA features from the database and identifies systematic gaps
the user keeps making. Example: "63% of your debug prompts lack error messages."

This is NOT template-based. It uses the user's OWN history to find patterns,
making suggestions personalized rather than generic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskPattern:
    """Analysis of prompts for a single task type."""

    task_type: str
    count: int
    avg_score: float
    # Feature gap rates (0.0 = always present, 1.0 = always missing)
    gaps: list[FeatureGap] = field(default_factory=list)


@dataclass
class FeatureGap:
    """A frequently missing feature for a task type."""

    feature: str
    label: str  # human-readable
    missing_rate: float  # 0.0-1.0
    impact: str  # "high", "medium", "low"
    suggestion: str  # actionable advice


@dataclass
class PatternsReport:
    """Complete personal prompt patterns analysis."""

    total_analyzed: int
    task_distribution: dict[str, int]  # task_type → count
    patterns: list[TaskPattern]
    top_gaps: list[FeatureGap]  # cross-task most common gaps


# Feature checks: (field_name, human_label, applicable_task_types, impact)
_FEATURE_CHECKS: list[tuple[str, str, list[str], str]] = [
    ("has_error_messages", "error messages", ["debug"], "high"),
    ("has_file_references", "file references", ["debug", "implement", "refactor", "test"], "high"),
    ("has_code_blocks", "code blocks", ["debug", "implement"], "medium"),
    ("has_constraints", "constraints", ["implement", "refactor", "review"], "high"),
    ("has_io_spec", "I/O specifications", ["implement", "test"], "medium"),
    ("has_edge_cases", "edge cases", ["implement", "test"], "medium"),
    ("has_examples", "examples", ["implement", "test"], "medium"),
    ("has_output_format", "output format", ["implement", "review", "summarize"], "low"),
    ("has_role_definition", "role definition", ["review", "creative"], "low"),
    ("has_step_by_step", "step-by-step structure", ["implement", "refactor"], "low"),
]

_SUGGESTIONS: dict[str, str] = {
    "has_error_messages": 'Include the error message: "Error: <paste stack trace>"',
    "has_file_references": 'Reference files: "in src/auth/middleware.ts"',
    "has_code_blocks": "Paste the relevant code in a ``` block",
    "has_constraints": 'Add constraints: "Do not modify existing tests"',
    "has_io_spec": 'Specify input/output: "Takes a user ID, returns a JWT token"',
    "has_edge_cases": 'Mention edge cases: "Handle empty input and null values"',
    "has_examples": "Add an example of expected input/output",
    "has_output_format": 'Specify format: "Return as JSON with fields..."',
    "has_role_definition": 'Set a role: "You are a security-focused code reviewer"',
    "has_step_by_step": 'Request steps: "Break this into incremental steps"',
}


def analyze_patterns(
    db: Any,
    *,
    source: str | None = None,
    limit: int = 500,
) -> PatternsReport:
    """Analyze personal prompt patterns from stored PromptDNA features."""
    conn = db._conn()
    try:
        if source:
            rows = conn.execute(
                "SELECT pf.features_json, pf.overall_score, pf.task_type "
                "FROM prompt_features pf "
                "JOIN prompts p ON pf.prompt_hash = p.hash "
                "WHERE p.source = ? "
                "ORDER BY pf.rowid DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT features_json, overall_score, task_type "
                "FROM prompt_features "
                "ORDER BY rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        return PatternsReport(
            total_analyzed=0,
            task_distribution={},
            patterns=[],
            top_gaps=[],
        )

    # Parse features and group by task type
    by_task: dict[str, list[dict[str, Any]]] = {}
    task_scores: dict[str, list[float]] = {}

    for row in rows:
        features = json.loads(row["features_json"])
        task = row["task_type"] or "other"
        by_task.setdefault(task, []).append(features)
        task_scores.setdefault(task, []).append(float(row["overall_score"] or 0))

    task_distribution = {t: len(prompts) for t, prompts in by_task.items()}

    # Analyze each task type
    patterns: list[TaskPattern] = []
    all_gaps: list[FeatureGap] = []

    for task_type, feature_list in by_task.items():
        count = len(feature_list)
        if count < 3:  # need enough data for meaningful patterns
            continue

        avg_score = sum(task_scores[task_type]) / count
        gaps: list[FeatureGap] = []

        for field_name, label, applicable_tasks, impact in _FEATURE_CHECKS:
            if task_type not in applicable_tasks:
                continue

            # Count how often this feature is missing
            missing = sum(1 for f in feature_list if not f.get(field_name, False))
            missing_rate = missing / count

            # Only report if missing >40% of the time
            if missing_rate > 0.4:
                gap = FeatureGap(
                    feature=field_name,
                    label=label,
                    missing_rate=round(missing_rate, 2),
                    impact=impact,
                    suggestion=_SUGGESTIONS.get(field_name, f"Add {label}"),
                )
                gaps.append(gap)
                all_gaps.append(gap)

        # Sort by missing rate descending
        gaps.sort(key=lambda g: g.missing_rate, reverse=True)

        patterns.append(
            TaskPattern(
                task_type=task_type,
                count=count,
                avg_score=round(avg_score, 1),
                gaps=gaps[:5],  # top 5 gaps per task
            )
        )

    # Sort patterns by count (most common task types first)
    patterns.sort(key=lambda p: p.count, reverse=True)

    # Deduplicate and sort top_gaps across all tasks
    seen: set[str] = set()
    top_gaps: list[FeatureGap] = []
    all_gaps.sort(key=lambda g: g.missing_rate, reverse=True)
    for gap in all_gaps:
        if gap.feature not in seen:
            seen.add(gap.feature)
            top_gaps.append(gap)

    return PatternsReport(
        total_analyzed=len(rows),
        task_distribution=task_distribution,
        patterns=patterns,
        top_gaps=top_gaps[:5],
    )
