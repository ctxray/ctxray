"""MCP server for reprompt — exposes prompt analytics as 6 focused tools.

Usage:
    python -m reprompt.mcp          # stdio transport (default)
    reprompt mcp-serve               # via CLI

Register in Claude Code (.mcp.json):
    {
        "mcpServers": {
            "reprompt": {
                "type": "stdio",
                "command": "reprompt",
                "args": ["mcp-serve"]
            }
        }
    }
"""

from __future__ import annotations

import json
import logging

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP(name="reprompt")


def _get_db():  # type: ignore[no-untyped-def]
    """Lazy-load DB to avoid import overhead on every tool call."""
    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    return PromptDB(settings.db_path), settings


# ─── Tools ──────────────────────────────────────────────────────────────────


@mcp.tool
def search_prompts(
    query: str | None = None,
    category: str | None = None,
    top: bool = False,
    limit: int = 10,
) -> str:
    """Search your prompt history and pattern library.

    This is the unified search tool — use it to find past prompts by keyword,
    browse prompt patterns by category, or get your most effective prompts.

    Examples:
        - search_prompts(query="auth") → find prompts mentioning "auth"
        - search_prompts(category="debug") → browse debug patterns
        - search_prompts(category="test", top=True) → best testing patterns
        - search_prompts(top=True, limit=5) → top 5 patterns across all categories

    Args:
        query: Keyword to search in prompt history (case-insensitive). If omitted,
               returns prompt patterns instead of raw prompts.
        category: Filter patterns by category (debug/implement/test/review/refactor/
                  explain/config). Only used when query is omitted.
        top: When True, sort patterns by frequency to surface most effective ones.
             Only used when query is omitted.
        limit: Maximum results to return (default 10)
    """
    try:
        db, _ = _get_db()

        # Keyword search mode: search raw prompt history
        if query is not None:
            results = db.search_prompts(query, limit=limit)
            if not results:
                return f"No prompts matching '{query}'"
            items = []
            for r in results:
                items.append(
                    {
                        "text": r["text"],
                        "source": r.get("source", ""),
                        "project": r.get("project", ""),
                        "date": (r.get("timestamp") or "")[:10],
                    }
                )
            return json.dumps(items, indent=2)

        # Pattern browse mode: search the pattern library
        patterns = db.get_patterns(category=category)
        if top:
            patterns = sorted(patterns, key=lambda p: p.get("frequency", 0), reverse=True)
        items = []
        for p in patterns[:limit]:
            items.append(
                {
                    "pattern": p["pattern_text"],
                    "frequency": p["frequency"],
                    "category": p["category"],
                    "avg_length": p.get("avg_length", 0),
                }
            )
        if not items:
            msg = f"No patterns in category '{category}'" if category else "No patterns yet"
            return f"{msg}. Run `reprompt scan` first."
        return json.dumps(items, indent=2)
    except Exception as exc:
        logger.debug("search_prompts error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool
def compare_prompts(prompt_a: str, prompt_b: str) -> str:
    """Compare two prompts side by side using research-backed Prompt DNA analysis.

    Returns scores and feature differences for both prompts, showing which
    is stronger and why. Useful for choosing between two phrasings.

    Args:
        prompt_a: First prompt text
        prompt_b: Second prompt text
    """
    try:
        from reprompt.core.extractors import extract_features
        from reprompt.core.scorer import score_prompt as _score

        dna_a = extract_features(prompt_a, source="mcp", session_id="mcp-compare")
        dna_b = extract_features(prompt_b, source="mcp", session_id="mcp-compare")
        score_a = _score(dna_a)
        score_b = _score(dna_b)

        def _fmt(dna, score):  # type: ignore[no-untyped-def]
            return {
                "total": score.total,
                "structure": score.structure,
                "context": score.context,
                "position": score.position,
                "repetition": score.repetition,
                "clarity": score.clarity,
                "task_type": dna.task_type,
                "word_count": dna.word_count,
            }

        winner = "A" if score_a.total >= score_b.total else "B"
        return json.dumps(
            {
                "prompt_a": _fmt(dna_a, score_a),
                "prompt_b": _fmt(dna_b, score_b),
                "winner": winner,
                "difference": abs(score_a.total - score_b.total),
            },
            indent=2,
        )
    except Exception as exc:
        logger.debug("compare_prompts error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool
def compress_prompt(text: str) -> str:
    """Compress a prompt by removing filler words, simplifying phrases, and cleaning structure.

    Returns the compressed text with token savings. Uses 4-layer rule-based
    compression — no LLM needed. Typical savings: 20-50%.

    Args:
        text: The prompt text to compress
    """
    try:
        from reprompt.core.compress import compress_prompt as _compress

        result = _compress(text)
        return json.dumps(
            {
                "original": result.original,
                "compressed": result.compressed,
                "original_tokens": result.original_tokens,
                "compressed_tokens": result.compressed_tokens,
                "savings_pct": result.savings_pct,
                "changes": result.changes,
            },
            indent=2,
        )
    except Exception as exc:
        logger.debug("compress_prompt error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool
def score_prompt(text: str) -> str:
    """Score a prompt using research-backed analysis (0-100).

    Returns a breakdown across 5 dimensions: structure, context,
    position, repetition, clarity. Based on 4 academic papers.

    Args:
        text: The prompt text to score
    """
    try:
        from reprompt.core.cost import estimate_cost, format_cost
        from reprompt.core.extractors import extract_features
        from reprompt.core.scorer import score_prompt as _score

        dna = extract_features(text, source="mcp", session_id="mcp-score")
        breakdown = _score(dna)
        cost_usd = estimate_cost(dna.token_count, source="mcp")
        return json.dumps(
            {
                "total": breakdown.total,
                "structure": breakdown.structure,
                "context": breakdown.context,
                "position": breakdown.position,
                "repetition": breakdown.repetition,
                "clarity": breakdown.clarity,
                "task_type": dna.task_type,
                "token_count": dna.token_count,
                "estimated_cost": format_cost(cost_usd),
                "suggestions": [
                    {"message": s.message, "impact": s.impact} for s in breakdown.suggestions[:3]
                ],
            },
            indent=2,
        )
    except Exception as exc:
        logger.debug("score_prompt error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool
def check_privacy(limit: int = 100) -> str:
    """Scan stored prompts for sensitive content (API keys, tokens, PII).

    Returns a summary of sensitive content found in your prompt history,
    categorized by type (API keys, emails, IP addresses, etc.).

    Args:
        limit: Maximum prompts to scan (default 100, most recent)
    """
    try:
        from reprompt.core.privacy_scan import scan_prompts

        db, _ = _get_db()
        rows = db.get_recent_prompts(limit=limit)
        prompts = [
            {"text": r["text"], "source": r.get("source", "unknown"), "id": r.get("id")}
            for r in rows
        ]
        result = scan_prompts(prompts)
        return json.dumps(
            {
                "prompts_scanned": result.prompts_scanned,
                "total_findings": len(result.matches),
                "categories": result.category_counts,
                "highest_risk": (
                    {
                        "category": result.highest_risk.category,
                        "source": result.highest_risk.source,
                    }
                    if result.highest_risk
                    else None
                ),
            },
            indent=2,
        )
    except Exception as exc:
        logger.debug("check_privacy error: %s", exc)
        return json.dumps({"error": str(exc)})


@mcp.tool
def scan_sessions(source: str | None = None) -> str:
    """Scan AI coding sessions for new prompts.

    Scans session files, deduplicates, and stores unique prompts.
    Runs incrementally — only processes new sessions since last scan.

    Args:
        source: Specific source to scan (claude-code, openclaw). Scans all if omitted.
    """
    try:
        from reprompt.core.pipeline import run_scan

        _, settings = _get_db()
        result = run_scan(source=source, settings=settings)
        return json.dumps(
            {
                "sessions_scanned": result.sessions_scanned,
                "prompts_found": result.total_parsed,
                "unique": result.unique_after_dedup,
                "duplicates": result.duplicates,
                "new_stored": result.new_stored,
            },
            indent=2,
        )
    except Exception as exc:
        logger.debug("scan_sessions error: %s", exc)
        return json.dumps({"error": str(exc)})


# ─── Resources ──────────────────────────────────────────────────────────────


@mcp.resource("reprompt://status")
def resource_status() -> str:
    """Current reprompt database status."""
    db, _ = _get_db()
    return json.dumps(db.get_stats(), indent=2)


@mcp.resource("reprompt://library")
def resource_library() -> str:
    """Full prompt pattern library."""
    db, _ = _get_db()
    patterns = db.get_patterns()
    items = [
        {
            "pattern": p["pattern_text"],
            "frequency": p["frequency"],
            "category": p["category"],
        }
        for p in patterns
    ]
    return json.dumps(items, indent=2)


# ─── Entry point ────────────────────────────────────────────────────────────


def run_server() -> None:
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    run_server()
