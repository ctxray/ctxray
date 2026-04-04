"""Message handler for Native Messaging bridge.

Processes incoming messages from the browser extension:
- ping -> pong (health check)
- sync_prompts -> store in DB, return counts + lightweight insights
- get_status -> return DB stats
- get_insights -> return full analysis (repetition, patterns, top insight)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ctxray import __version__
from ctxray.adapters.filters import should_keep_prompt
from ctxray.storage.db import PromptDB

logger = logging.getLogger(__name__)


def handle_message(message: dict[str, Any], db: PromptDB) -> dict[str, Any]:
    """Process a single message and return a response dict."""
    msg_type = message.get("type", "")

    if msg_type == "ping":
        return {"type": "pong", "version": __version__}

    if msg_type == "sync_prompts":
        return _handle_sync(message, db)

    if msg_type == "get_status":
        return _handle_status(db)

    if msg_type == "get_insights":
        return _handle_insights(message, db)

    return {"type": "error", "message": f"Unknown message type: {msg_type}"}


def _handle_sync(message: dict[str, Any], db: PromptDB) -> dict[str, Any]:
    """Store synced prompts in DB, skipping noise and duplicates."""
    prompts = message.get("prompts", [])
    received = len(prompts)
    new_stored = 0
    duplicates = 0

    for p in prompts:
        text = p.get("text", "").strip()
        if not should_keep_prompt(text):
            continue

        source = p.get("source", "extension")
        session_id = p.get("conversation_id", "")
        project = p.get("conversation_title", "")
        timestamp = p.get("timestamp", "")

        inserted = db.insert_prompt(
            text,
            source=source,
            project=project,
            session_id=session_id,
            timestamp=timestamp,
        )
        if inserted:
            new_stored += 1
        else:
            duplicates += 1

    # Record last sync time
    _update_last_sync(db)

    return {
        "type": "sync_result",
        "received": received,
        "new_stored": new_stored,
        "duplicates": duplicates,
        "insights": _compute_quick_insights(db),
    }


def _handle_status(db: PromptDB) -> dict[str, Any]:
    """Return current database stats."""
    stats = db.get_stats()
    return {
        "type": "status",
        "total_prompts": stats.get("total_prompts", 0),
        "last_sync": _get_last_sync(db),
        "version": __version__,
    }


def _handle_insights(message: dict[str, Any], db: PromptDB) -> dict[str, Any]:
    """Return full analysis: repetition, effectiveness patterns, insights.

    Heavier computation than sync — call on-demand, not every sync.
    """
    source = message.get("source")
    result: dict[str, Any] = {"type": "insights_result"}

    try:
        from ctxray.core.insights import (
            compute_insights,
            get_cross_session_repetition_insight,
            get_effectiveness_insight,
        )

        features = db.get_all_features(source=source)
        if features:
            full = compute_insights(features)
            result["avg_score"] = full.get("avg_score", 0.0)
            result["prompt_count"] = full.get("prompt_count", 0)
            result["score_distribution"] = full.get("score_distribution", {})
            result["insights"] = [
                {"category": i["category"], "action": i["action"], "impact": i["impact"]}
                for i in full.get("insights", [])
            ]
        else:
            result["avg_score"] = 0.0
            result["prompt_count"] = 0
            result["score_distribution"] = {}
            result["insights"] = []

        # Repetition (may be None if insufficient data)
        rep = get_cross_session_repetition_insight(db, source=source)
        if rep:
            result["repetition"] = {
                "rate": rep["repetition_rate"],
                "top_topics": rep["top_topics"],
                "total_recurring": rep["total_recurring_topics"],
            }

        # Effectiveness patterns (may be None)
        eff = get_effectiveness_insight(db, source=source)
        if eff:
            result["effectiveness"] = {
                "top_patterns": eff["top_patterns"],
                "total_patterns": eff["total_patterns"],
            }

    except Exception:
        logger.warning("Failed to compute full insights for extension", exc_info=True)
        result["error"] = "Failed to compute insights"

    return result


def _compute_quick_insights(db: PromptDB) -> dict[str, Any]:
    """Lightweight stats for extension display. Pure SQL, no heavy computation."""
    stats = db.get_stats()
    total = stats.get("total_prompts", 0)

    if total == 0:
        return {
            "avg_score": 0.0,
            "total_prompts": 0,
            "score_trend": "stable",
            "top_insight": None,
        }

    scores = db.get_recent_scores(limit=50)

    if not scores:
        return {
            "avg_score": 0.0,
            "total_prompts": total,
            "score_trend": "stable",
            "top_insight": None,
        }

    avg_score = round(sum(scores) / len(scores), 1)

    # Trend: compare first half (recent) vs second half (older)
    mid = len(scores) // 2
    if mid >= 5:
        recent_avg = sum(scores[:mid]) / mid
        older_avg = sum(scores[mid:]) / (len(scores) - mid)
        diff = recent_avg - older_avg
        if diff > 3:
            trend = "improving"
        elif diff < -3:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Top insight: get highest-impact actionable tip
    top_insight = _get_top_insight(db)

    return {
        "avg_score": avg_score,
        "total_prompts": total,
        "score_trend": trend,
        "top_insight": top_insight,
    }


def _get_top_insight(db: PromptDB) -> str | None:
    """Return the single most impactful insight as a string, or None."""
    try:
        from ctxray.core.insights import compute_insights

        features = db.get_all_features()
        if len(features) < 5:
            return None
        result = compute_insights(features)
        insights = result.get("insights", [])
        # Prioritize high-impact insights
        for impact in ("high", "medium", "low"):
            for i in insights:
                if i.get("impact") == impact:
                    return i["action"]
    except Exception:
        logger.debug("Failed to compute top insight", exc_info=True)
    return None


def _update_last_sync(db: PromptDB) -> None:
    """Store last sync timestamp in the DB settings table."""
    now_ts = str(int(datetime.now(tz=timezone.utc).timestamp()))
    db.set_setting("last_extension_sync", now_ts)


def _get_last_sync(db: PromptDB) -> str:
    """Get last sync timestamp. Returns empty string if never synced."""
    val = db.get_setting("last_extension_sync")
    if val:
        try:
            return datetime.fromtimestamp(int(val), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OSError):
            return ""
    return ""
