"""Time-window query utilities shared across retention features."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class TimeWindow:
    """A half-open time interval [start, end)."""

    start: datetime
    end: datetime
    label: str  # e.g. "2026-W10", "Mar 03-09"


def parse_period(period: str) -> timedelta:
    """Parse '7d', '4w', '1m', '1y' into a timedelta.

    Raises ValueError for invalid input.
    """
    m = re.fullmatch(r"(\d+)([dwmy])", period.strip().lower())
    if not m:
        raise ValueError(f"Invalid period: {period!r}. Use 7d, 4w, 1m, etc.")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return timedelta(days=n)
    if unit == "w":
        return timedelta(weeks=n)
    if unit == "m":
        return timedelta(days=n * 30)
    if unit == "y":
        return timedelta(days=n * 365)
    raise ValueError(f"Unknown unit: {unit}")  # pragma: no cover


def sliding_windows(
    period: str = "7d",
    count: int = 4,
    anchor: datetime | None = None,
) -> list[TimeWindow]:
    """Generate ``count`` consecutive windows of ``period`` length ending at ``anchor``.

    Returns windows in chronological order (oldest first).
    """
    if anchor is None:
        anchor = datetime.now(timezone.utc)
    delta = parse_period(period)
    windows: list[TimeWindow] = []
    for i in range(count - 1, -1, -1):
        end = anchor - delta * i
        start = end - delta
        label = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
        windows.append(TimeWindow(start=start, end=end, label=label))
    return windows
