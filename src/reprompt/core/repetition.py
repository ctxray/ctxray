"""Cross-session prompt repetition detection.

Identifies recurring topics asked across different AI coding sessions
using TF-IDF + containment similarity clustering. All analysis is
rule-based (zero LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from reprompt.storage.db import PromptDB


@dataclass
class RecurringTopic:
    """A topic that recurs across multiple sessions."""

    canonical_text: str
    session_count: int
    total_matches: int
    session_ids: list[str] = field(default_factory=list)
    earliest: str = ""
    latest: str = ""


@dataclass
class RepetitionReport:
    """Result of cross-session repetition analysis."""

    total_prompts_analyzed: int = 0
    cross_session_matches: int = 0
    repetition_rate: float = 0.0  # cross_session_matches / total
    recurring_topics: list[RecurringTopic] = field(default_factory=list)
    total_sessions: int = 0


def analyze_repetition(
    db: PromptDB,
    source: str | None = None,
    limit: int = 500,
    threshold: float = 0.75,
) -> RepetitionReport:
    """Detect recurring prompts across different sessions.

    Reuses merge_view.build_clusters() for similarity, then filters
    to clusters spanning 2+ distinct sessions.
    """
    from reprompt.core.merge_view import build_clusters

    all_prompts = db.get_all_prompts(source=source)

    # Filter to unique prompts only
    unique = [p for p in all_prompts if p.get("duplicate_of") is None]

    if not unique:
        return RepetitionReport()

    # Limit to most recent N (by id desc), then reverse for chronological
    unique.sort(key=lambda p: p.get("id", 0), reverse=True)
    unique = unique[:limit]
    unique.reverse()

    # Build lookup: text → prompt dict (safe due to hash uniqueness)
    text_to_prompt: dict[str, dict[str, Any]] = {}
    for p in unique:
        text_to_prompt[p["text"]] = p

    texts = [p["text"] for p in unique]
    timestamps = [p.get("timestamp", "") for p in unique]
    all_session_ids = {p.get("session_id") or "unknown" for p in unique}

    # Build clusters using existing infrastructure
    clusters = build_clusters(texts, timestamps, threshold=threshold)

    # Filter to cross-session clusters
    recurring: list[RecurringTopic] = []
    total_cross_matches = 0

    for cluster in clusters:
        # Collect all texts in cluster (canonical + members)
        cluster_texts = [cluster["canonical"]["text"]]
        cluster_texts.extend(m["text"] for m in cluster["members"])

        # Map to session_ids
        sids: list[str] = []
        cluster_timestamps: list[str] = []
        for t in cluster_texts:
            prompt = text_to_prompt.get(t)
            if prompt:
                sids.append(prompt.get("session_id") or "unknown")
                cluster_timestamps.append(prompt.get("timestamp", ""))

        distinct_sessions = sorted(set(sids))
        if len(distinct_sessions) < 2:
            continue

        # Build timestamps for range
        valid_ts = sorted(t for t in cluster_timestamps if t)
        earliest = valid_ts[0] if valid_ts else ""
        latest = valid_ts[-1] if valid_ts else ""

        recurring.append(
            RecurringTopic(
                canonical_text=cluster["canonical"]["text"],
                session_count=len(distinct_sessions),
                total_matches=len(cluster_texts),
                session_ids=distinct_sessions,
                earliest=earliest,
                latest=latest,
            )
        )
        total_cross_matches += len(cluster_texts)

    # Sort by session_count desc, then total_matches desc
    recurring.sort(key=lambda t: (-t.session_count, -t.total_matches))

    total = len(unique)
    rate = total_cross_matches / total if total > 0 else 0.0

    return RepetitionReport(
        total_prompts_analyzed=total,
        cross_session_matches=total_cross_matches,
        repetition_rate=round(rate, 3),
        recurring_topics=recurring,
        total_sessions=len(all_session_ids),
    )
