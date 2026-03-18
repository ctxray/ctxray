# src/reprompt/core/insights.py
"""Personal insights engine — compares user patterns against research-optimal.

Analyzes stored PromptDNA features to surface actionable, research-backed
insights about the user's prompting patterns.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# Research-optimal thresholds (from papers)
OPTIMAL = {
    "key_instruction_position": 0.15,  # front-loaded (Lost in the Middle)
    "keyword_repetition_freq": 0.3,  # moderate repetition (Google 2512.14982)
    "context_specificity": 0.6,  # high specificity (DETAIL)
    "constraint_pct": 0.67,  # 67% of prompts should have constraints
    "ambiguity_score": 0.2,  # low ambiguity
}


def compute_insights(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate insights from stored feature vectors.

    Returns dict with: prompt_count, avg_score, best_task_type, worst_task_type,
    score_distribution, insights (list of actionable findings).
    """
    if not features:
        return {
            "prompt_count": 0,
            "avg_score": 0.0,
            "best_task_type": {"type": "none", "avg_score": 0.0},
            "worst_task_type": {"type": "none", "avg_score": 0.0},
            "score_distribution": {},
            "source_scores": {},
            "insights": [],
        }

    count = len(features)
    scores = [f.get("overall_score", 0.0) for f in features]
    avg_score = sum(scores) / count

    # -- Score distribution --
    distribution: dict[str, int] = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20:
            distribution["0-20"] += 1
        elif s <= 40:
            distribution["21-40"] += 1
        elif s <= 60:
            distribution["41-60"] += 1
        elif s <= 80:
            distribution["61-80"] += 1
        else:
            distribution["81-100"] += 1

    # -- Per-task-type stats --
    by_type: dict[str, list[float]] = defaultdict(list)
    for f in features:
        tt = f.get("task_type", "other")
        by_type[tt].append(f.get("overall_score", 0.0))

    type_avgs = {t: sum(s) / len(s) for t, s in by_type.items() if s}
    best_type = max(type_avgs, key=type_avgs.__getitem__) if type_avgs else "none"
    worst_type = min(type_avgs, key=type_avgs.__getitem__) if type_avgs else "none"

    # -- Generate insights --
    insights: list[dict[str, Any]] = []

    # Insight 1: Instruction position
    positions = [f.get("key_instruction_position", 0.0) for f in features]
    mid_buried_pct = sum(1 for p in positions if 0.3 < p < 0.7) / count
    if mid_buried_pct > 0.3:
        insights.append(
            {
                "category": "position",
                "paper": "Lost in the Middle arXiv:2307.03172",
                "finding": f"You: {mid_buried_pct:.0%} of prompts have instructions in the middle",
                "optimal": "Research says: start or end position is 2-3x better",
                "action": "Move your main instruction to the first sentence",
                "impact": "high",
            }
        )

    # Insight 2: Keyword repetition
    reps = [f.get("keyword_repetition_freq", 0.0) for f in features]
    avg_rep = sum(reps) / count
    if avg_rep < OPTIMAL["keyword_repetition_freq"] and count >= 5:
        insights.append(
            {
                "category": "repetition",
                "paper": "Google Research arXiv:2512.14982",
                "finding": f"You: {avg_rep:.2f} avg repetition",
                "optimal": f"Research optimal: {OPTIMAL['keyword_repetition_freq']}+ (repeat once)",
                "action": "Echo your main requirement at the end of long prompts",
                "impact": "medium",
            }
        )

    # Insight 3: Context specificity
    specs = [f.get("context_specificity", 0.0) for f in features]
    avg_spec = sum(specs) / count
    if avg_spec < OPTIMAL["context_specificity"] and count >= 5:
        insights.append(
            {
                "category": "context",
                "paper": "DETAIL arXiv:2512.02246",
                "finding": f"You: {avg_spec:.2f} avg specificity",
                "optimal": (
                    f"Top performers: {OPTIMAL['context_specificity']}+ (include code/errors)"
                ),
                "action": (
                    "Include actual code snippets and error messages instead of describing them"
                ),
                "impact": "high",
            }
        )

    # Insight 4: Constraint usage
    constraint_pct = sum(1 for f in features if f.get("has_constraints")) / count
    if constraint_pct < OPTIMAL["constraint_pct"] and count >= 5:
        insights.append(
            {
                "category": "structure",
                "paper": "The Prompt Report arXiv:2406.06608",
                "finding": f"You: {constraint_pct:.0%} of prompts have constraints",
                "optimal": f"Top 10%: {OPTIMAL['constraint_pct']:.0%} have constraints",
                "action": 'Add "Do not..." / "Must..." to narrow output scope',
                "impact": "medium",
            }
        )

    # Insight 5: Ambiguity
    ambiguities = [f.get("ambiguity_score", 0.0) for f in features]
    avg_ambiguity = sum(ambiguities) / count
    if avg_ambiguity > OPTIMAL["ambiguity_score"] and count >= 5:
        insights.append(
            {
                "category": "clarity",
                "paper": "DETAIL arXiv:2512.02246",
                "finding": f"You: {avg_ambiguity:.2f} avg ambiguity score",
                "optimal": f"Research optimal: <{OPTIMAL['ambiguity_score']}",
                "action": 'Replace vague words ("it", "this", "something") with specific names',
                "impact": "medium",
            }
        )

    # -- Per-source breakdown --
    by_source: dict[str, list[float]] = defaultdict(list)
    for f in features:
        src = f.get("source", "unknown")
        by_source[src].append(f.get("overall_score", 0.0))

    source_avgs = {
        s: round(sum(scores_list) / len(scores_list), 1)
        for s, scores_list in by_source.items()
        if len(scores_list) >= 3
    }

    return {
        "prompt_count": count,
        "avg_score": round(avg_score, 1),
        "best_task_type": {
            "type": best_type,
            "avg_score": round(type_avgs.get(best_type, 0.0), 1),
        },
        "worst_task_type": {
            "type": worst_type,
            "avg_score": round(type_avgs.get(worst_type, 0.0), 1),
        },
        "score_distribution": distribution,
        "source_scores": source_avgs,
        "insights": insights,
    }
