"""Weekly digest — compares current vs previous period activity."""

from __future__ import annotations

from typing import Any

from ctxray.core.timeutil import sliding_windows
from ctxray.core.trends import compute_window_snapshot
from ctxray.storage.db import PromptDB


def build_digest(db: PromptDB, period: str = "7d", source: str | None = None) -> dict[str, Any]:
    """Compare current period vs previous period.

    Returns dict with:
      period, current (snapshot dict), previous (snapshot dict),
      count_delta (int), spec_delta (float), summary (str for --quiet)
    """
    # Two consecutive windows: [older, current]
    windows = sliding_windows(period=period, count=2)
    prev_window = windows[0]
    curr_window = windows[1]

    current = compute_window_snapshot(db, curr_window, period, source=source)
    previous = compute_window_snapshot(db, prev_window, period, source=source)

    count_delta = current["prompt_count"] - previous["prompt_count"]
    spec_delta = round(current["specificity_score"] - previous["specificity_score"], 2)

    # Effectiveness summary (None if no session data)
    eff_summary = db.get_effectiveness_summary()
    eff_avg: float | None = eff_summary.get("avg_score") if eff_summary.get("total") else None

    # One-liner summary for --quiet mode / digest_log
    sign = "+" if count_delta > 0 else ""
    # 0.01 noise floor — ignore tiny floating-point drift
    arrow = "↑" if spec_delta > 0.01 else ("↓" if spec_delta < -0.01 else "→")
    summary = (
        f"ctxray: {current['prompt_count']} prompts ({sign}{count_delta}),"
        f" specificity {current['specificity_score']:.2f} ({arrow})"
    )
    if eff_avg is not None:
        summary += f", quality {eff_avg:.2f}"

    # Log this digest run (skip for source-filtered runs to preserve unfiltered history)
    if not source:
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
        "eff_avg": eff_avg,
        "summary": summary,
    }
