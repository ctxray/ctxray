"""Weekly digest — compares current vs previous period activity."""

from __future__ import annotations

from typing import Any

from reprompt.core.timeutil import sliding_windows
from reprompt.core.trends import compute_window_snapshot
from reprompt.storage.db import PromptDB


def build_digest(db: PromptDB, period: str = "7d") -> dict[str, Any]:
    """Compare current period vs previous period.

    Returns dict with:
      period, current (snapshot dict), previous (snapshot dict),
      count_delta (int), spec_delta (float), summary (str for --quiet)
    """
    # Two consecutive windows: [older, current]
    windows = sliding_windows(period=period, count=2)
    prev_window = windows[0]
    curr_window = windows[1]

    current = compute_window_snapshot(db, curr_window, period)
    previous = compute_window_snapshot(db, prev_window, period)

    count_delta = current["prompt_count"] - previous["prompt_count"]
    spec_delta = round(current["specificity_score"] - previous["specificity_score"], 2)

    # One-liner summary for --quiet mode / digest_log
    sign = "+" if count_delta > 0 else ""
    # 0.01 noise floor — ignore tiny floating-point drift
    arrow = "↑" if spec_delta > 0.01 else ("↓" if spec_delta < -0.01 else "→")
    summary = (
        f"reprompt: {current['prompt_count']} prompts ({sign}{count_delta}),"
        f" specificity {current['specificity_score']:.2f} ({arrow})"
    )

    # Log this digest run
    db.log_digest(
        period=period,
        window_start=curr_window.start.isoformat(),
        window_end=curr_window.end.isoformat(),
        summary=summary,
    )

    return {
        "period": period,
        "current": current,
        "previous": previous,
        "count_delta": count_delta,
        "spec_delta": spec_delta,
        "summary": summary,
    }
