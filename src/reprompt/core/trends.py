"""Prompt evolution tracking — compute per-window metrics and trend insights."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from reprompt.core.library import categorize_prompt
from reprompt.core.timeutil import TimeWindow, sliding_windows
from reprompt.storage.db import PromptDB


def compute_window_snapshot(
    db: PromptDB,
    window: TimeWindow,
    period: str,
) -> dict[str, Any]:
    """Query prompts in a time window and compute aggregate metrics."""
    start_iso = window.start.isoformat()
    end_iso = window.end.isoformat()

    prompts = db.get_prompts_in_range(start_iso, end_iso)

    prompt_count = len(prompts)
    if prompt_count == 0:
        return {
            "window_start": start_iso,
            "window_end": end_iso,
            "window_label": window.label,
            "period": period,
            "prompt_count": 0,
            "unique_count": 0,
            "avg_length": 0.0,
            "median_length": 0.0,
            "vocab_size": 0,
            "specificity_score": 0.0,
            "category_distribution": {},
            "top_terms": [],
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    texts = [p["text"] for p in prompts]
    lengths = [p["char_count"] or len(p["text"]) for p in prompts]

    # Category distribution
    categories: Counter[str] = Counter()
    for t in texts:
        categories[categorize_prompt(t)] += 1

    # Vocabulary — unique non-trivial tokens
    all_tokens: set[str] = set()
    for t in texts:
        all_tokens.update(w.lower() for w in t.split() if len(w) > 2)
    vocab_size = len(all_tokens)

    # Specificity score
    avg_len = statistics.mean(lengths)
    specificity = _compute_specificity(avg_len, vocab_size, dict(categories))

    snapshot: dict[str, Any] = {
        "window_start": start_iso,
        "window_end": end_iso,
        "window_label": window.label,
        "period": period,
        "prompt_count": prompt_count,
        "unique_count": prompt_count,  # already filtered to unique in query
        "avg_length": round(avg_len, 1),
        "median_length": round(statistics.median(lengths), 1),
        "vocab_size": vocab_size,
        "specificity_score": round(specificity, 2),
        "category_distribution": dict(categories),
        "top_terms": [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store snapshot for future quick access
    db.upsert_snapshot(snapshot)
    return snapshot


def _compute_specificity(avg_length: float, vocab_size: int, categories: dict[str, int]) -> float:
    """Composite specificity score 0.0–1.0.

    Formula: 0.4 * norm(avg_length) + 0.3 * norm(vocab) + 0.3 * category_entropy
    """
    length_score = _norm(avg_length, 50, 500)
    vocab_score = _norm(vocab_size, 20, 200)

    total = sum(categories.values())
    if total == 0:
        entropy_score = 0.0
    else:
        probs = [c / total for c in categories.values() if c > 0]
        entropy = -sum(p * math.log2(p) for p in probs)
        max_entropy = math.log2(max(len(probs), 1)) if probs else 1.0
        entropy_score = entropy / max_entropy if max_entropy > 0 else 0.0

    return 0.4 * length_score + 0.3 * vocab_score + 0.3 * entropy_score


def _norm(x: float, lo: float, hi: float) -> float:
    """Clamp and scale x from [lo, hi] to [0, 1]."""
    return max(0.0, min(1.0, (x - lo) / (hi - lo))) if hi > lo else 0.0


def compute_trends(
    db: PromptDB,
    period: str = "7d",
    n_windows: int = 4,
) -> dict[str, Any]:
    """Compute snapshots for N consecutive windows and annotate deltas.

    Returns dict with "windows" list and "insights" list.
    """
    windows = sliding_windows(period=period, count=n_windows)
    snapshots: list[dict[str, Any]] = []

    for w in windows:
        snap = compute_window_snapshot(db, w, period)
        snapshots.append(snap)

    # Annotate deltas between consecutive windows
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        if prev["prompt_count"] > 0:
            delta_spec = curr["specificity_score"] - prev["specificity_score"]
            pct = (delta_spec / prev["specificity_score"] * 100) if prev["specificity_score"] else 0
            curr["specificity_delta"] = round(delta_spec, 2)
            curr["specificity_pct"] = round(pct)
        else:
            curr["specificity_delta"] = 0.0
            curr["specificity_pct"] = 0

    insights = generate_insights(snapshots)

    return {
        "period": period,
        "windows": snapshots,
        "insights": insights,
    }


def generate_insights(snapshots: list[dict[str, Any]]) -> list[str]:
    """Produce natural-language insights from trend data."""
    insights: list[str] = []
    active = [s for s in snapshots if s["prompt_count"] > 0]

    if len(active) < 2:
        if not active:
            insights.append("No prompt data found in this time range.")
        else:
            insights.append(f"Only 1 period with data ({active[0]['prompt_count']} prompts).")
        return insights

    first, last = active[0], active[-1]

    # Specificity trend
    spec_change = last["specificity_score"] - first["specificity_score"]
    if spec_change > 0.05:
        base = first["specificity_score"]
        pct = int(spec_change / base * 100) if base else 0
        n = len(active)
        insights.append(f"Your prompts are getting more specific (+{pct}% over {n} periods)")
    elif spec_change < -0.05:
        insights.append("Your prompt specificity has decreased — try being more detailed.")
    else:
        insights.append("Your prompt quality is consistent.")

    # Volume trend
    first_count = first["prompt_count"]
    last_count = last["prompt_count"]
    vol_change = last_count - first_count
    if vol_change > 0:
        insights.append(f"Activity is up: {first_count} → {last_count} prompts/period")
    elif vol_change < 0:
        insights.append(f"Activity is down: {first_count} → {last_count} prompts/period")

    # Category shifts
    first_cats = first.get("category_distribution", {})
    last_cats = last.get("category_distribution", {})
    if first_cats and last_cats:
        first_total = sum(first_cats.values())
        last_total = sum(last_cats.values())
        if first_total > 0 and last_total > 0:
            biggest_gain = ""
            biggest_gain_delta = 0.0
            for cat in set(list(first_cats.keys()) + list(last_cats.keys())):
                old_pct = first_cats.get(cat, 0) / first_total
                new_pct = last_cats.get(cat, 0) / last_total
                delta = new_pct - old_pct
                if delta > biggest_gain_delta:
                    biggest_gain = cat
                    biggest_gain_delta = delta
            if biggest_gain and biggest_gain_delta > 0.05:
                insights.append(
                    f"Category shift: '{biggest_gain}' usage increased by "
                    f"{int(biggest_gain_delta * 100)}%"
                )

    return insights
