"""Dashboard data builder for bare `reprompt` command."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from reprompt.core.pipeline import get_adapters
from reprompt.storage.db import PromptDB


@dataclass
class DashboardData:
    """Data for dashboard rendering."""

    has_data: bool = False

    # Zero state
    discoveries: list[dict[str, Any]] = field(default_factory=list)

    # Data state
    prompt_count: int = 0
    session_count: int = 0
    avg_score: dict[str, float] = field(default_factory=dict)
    avg_compressibility: float = 0.0
    long_sessions: int = 0  # sessions with 60+ turns


def _discover_sessions() -> list[dict[str, Any]]:
    """Discover AI tool sessions on disk without parsing them.

    Returns list of {adapter, sessions, turns_estimate}.
    """
    results = []
    for adapter in get_adapters():
        if not adapter.detect_installed():
            continue
        session_dir = Path(adapter.default_session_path).expanduser()
        if not session_dir.exists():
            continue

        # Count session files (adapter-specific patterns)
        if hasattr(adapter, "discover_sessions"):
            session_files = adapter.discover_sessions()
        else:
            session_files = list(session_dir.glob("*"))

        if not session_files:
            continue

        # Estimate turns: count lines for JSONL, or use heuristic
        turn_estimate = 0
        for f in session_files[:50]:  # Sample max 50 files
            try:
                if f.suffix == ".jsonl":
                    turn_estimate += sum(1 for _ in f.open())
                else:
                    # Rough heuristic: file size / 500 bytes per turn
                    turn_estimate += max(1, f.stat().st_size // 500)
            except OSError:
                pass

        results.append(
            {
                "adapter": adapter.name,
                "sessions": len(session_files),
                "turns_estimate": turn_estimate,
            }
        )

    return results


def _compute_avg_score(db: PromptDB) -> dict[str, float]:
    """Compute average scores from last 50 features in DB."""
    try:
        features = db.get_all_features()[:50]
    except Exception:
        return {"overall": 0}

    if not features:
        return {"overall": 0}

    scores: dict[str, list[float]] = {"overall": []}
    for f in features:
        overall = f.get("overall_score", 0)
        if overall:
            scores["overall"].append(overall)
        task = f.get("task_type", "")
        if task:
            scores.setdefault(task, []).append(overall)

    return {k: round(sum(v) / len(v)) if v else 0 for k, v in scores.items()}


def _compute_avg_compressibility(db: PromptDB) -> float:
    """Compute average compressibility from last 50 features."""
    try:
        features = db.get_all_features()[:50]
    except Exception:
        return 0.0

    vals = [f.get("compressibility", 0) for f in features if f.get("compressibility")]
    return sum(vals) / len(vals) if vals else 0.0


def build_dashboard_data(db: PromptDB) -> DashboardData:
    """Build dashboard data from DB + disk discovery."""
    stats = db.get_stats()
    total = stats.get("total_prompts", 0)

    if total == 0:
        # Zero state: discover what's on disk
        discoveries = _discover_sessions()
        return DashboardData(has_data=False, discoveries=discoveries)

    # Data state: query last 7 days
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    now_iso = now.isoformat()
    recent = db.get_prompts_in_range(week_ago, now_iso)

    # Count unique sessions in recent prompts
    session_ids = {p.get("session_id", "") for p in recent if p.get("session_id")}

    # Count long sessions (60+ prompts in a single session)
    long_sessions = 0
    try:
        conn = db._conn()
        try:
            rows = conn.execute(
                "SELECT session_id, COUNT(*) as cnt FROM prompts"
                " WHERE duplicate_of IS NULL GROUP BY session_id HAVING cnt >= 60"
            ).fetchall()
            long_sessions = len(rows)
        finally:
            conn.close()
    except Exception:
        pass

    return DashboardData(
        has_data=True,
        prompt_count=len(recent),
        session_count=len(session_ids),
        avg_score=_compute_avg_score(db),
        avg_compressibility=_compute_avg_compressibility(db),
        long_sessions=long_sessions,
    )
