"""Cross-tool comparison — aggregate prompt stats per AI tool.

Compares your prompting patterns across Claude Code, Cursor, ChatGPT, etc.
This is the signature "context intelligence" feature: no other tool can
analyze your usage across multiple AI tools locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ctxray.storage.db import PromptDB


@dataclass
class ToolStats:
    """Aggregate stats for a single AI tool (source)."""

    source: str
    prompt_count: int
    avg_words: float
    avg_score: float
    top_task_type: str
    error_context_rate: float  # fraction of debug prompts with errors
    file_ref_rate: float  # fraction of prompts with file path references


@dataclass
class ToolComparison:
    """Side-by-side comparison of tools with generated insights."""

    tools: list[ToolStats] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


def _aggregate_source(features: list[dict]) -> dict:
    """Compute aggregates over a list of feature vectors for one source."""
    if not features:
        return {
            "prompt_count": 0,
            "avg_words": 0.0,
            "avg_score": 0.0,
            "top_task_type": "-",
            "error_context_rate": 0.0,
            "file_ref_rate": 0.0,
        }

    n = len(features)
    total_words = sum(f.get("word_count", 0) for f in features)
    total_score = sum(f.get("overall_score", 0) for f in features)
    file_refs = sum(1 for f in features if f.get("has_file_path"))

    # Top task type
    task_counts: dict[str, int] = {}
    for f in features:
        t = f.get("task_type", "")
        if t:
            task_counts[t] = task_counts.get(t, 0) + 1
    top_task = max(task_counts.items(), key=lambda x: x[1])[0] if task_counts else "-"

    # Error context rate among debug prompts
    debug_prompts = [f for f in features if f.get("task_type") == "debug"]
    if debug_prompts:
        with_error = sum(1 for f in debug_prompts if f.get("has_error_message"))
        error_rate = with_error / len(debug_prompts)
    else:
        error_rate = 0.0

    return {
        "prompt_count": n,
        "avg_words": round(total_words / n, 1),
        "avg_score": round(total_score / n, 1),
        "top_task_type": top_task,
        "error_context_rate": round(error_rate, 3),
        "file_ref_rate": round(file_refs / n, 3),
    }


def _generate_insights(tools: list[ToolStats]) -> list[str]:
    """Generate comparison insights between tools (only when 2+ tools present)."""
    if len(tools) < 2:
        return []

    insights = []

    # Rank by avg score
    by_score = sorted(tools, key=lambda t: t.avg_score, reverse=True)
    best, worst = by_score[0], by_score[-1]
    if best.avg_score - worst.avg_score >= 5:
        insights.append(
            f"Your highest-scoring prompts come from {best.source} "
            f"({best.avg_score:.0f}/100), lowest from {worst.source} ({worst.avg_score:.0f}/100)"
        )

    # Prompt length differences
    by_words = sorted(tools, key=lambda t: t.avg_words, reverse=True)
    long_tool, short_tool = by_words[0], by_words[-1]
    if long_tool.avg_words - short_tool.avg_words >= 8:
        insights.append(
            f"Your {long_tool.source} prompts average {long_tool.avg_words:.0f} words — "
            f"{long_tool.avg_words - short_tool.avg_words:.0f} more than {short_tool.source} "
            f"({short_tool.avg_words:.0f} words)"
        )

    # File reference rate gap
    by_files = sorted(tools, key=lambda t: t.file_ref_rate, reverse=True)
    if by_files[0].file_ref_rate - by_files[-1].file_ref_rate >= 0.2:
        insights.append(
            f"You reference file paths in {by_files[0].file_ref_rate * 100:.0f}% of "
            f"{by_files[0].source} prompts vs {by_files[-1].file_ref_rate * 100:.0f}% on "
            f"{by_files[-1].source}"
        )

    # Error context gap (only if both tools have debug prompts)
    tools_with_debug = [t for t in tools if t.error_context_rate > 0]
    if len(tools_with_debug) >= 2:
        by_err = sorted(tools_with_debug, key=lambda t: t.error_context_rate, reverse=True)
        gap = (by_err[0].error_context_rate - by_err[-1].error_context_rate) * 100
        if gap >= 20:
            insights.append(
                f"Your debug prompts on {by_err[0].source} include error context "
                f"{gap:.0f}pp more often than on {by_err[-1].source}"
            )

    return insights


def build_tool_comparison(db: PromptDB) -> ToolComparison:
    """Build cross-tool comparison from DB."""
    # Find distinct sources
    conn = db._conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT source FROM prompts WHERE source != '' ORDER BY source"
        ).fetchall()
    finally:
        conn.close()

    sources = [r[0] for r in rows]

    tools = []
    for source in sources:
        features = db.get_all_features(source=source)
        agg = _aggregate_source(features)
        if agg["prompt_count"] == 0:
            continue
        tools.append(
            ToolStats(
                source=source,
                prompt_count=agg["prompt_count"],
                avg_words=agg["avg_words"],
                avg_score=agg["avg_score"],
                top_task_type=agg["top_task_type"],
                error_context_rate=agg["error_context_rate"],
                file_ref_rate=agg["file_ref_rate"],
            )
        )

    return ToolComparison(tools=tools, insights=_generate_insights(tools))
