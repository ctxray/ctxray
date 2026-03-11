"""MCP server for reprompt — exposes prompt analytics as tools and resources.

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

from fastmcp import FastMCP

mcp = FastMCP(name="reprompt")


def _get_db():  # type: ignore[no-untyped-def]
    """Lazy-load DB to avoid import overhead on every tool call."""
    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    return PromptDB(settings.db_path), settings


# ─── Tools ──────────────────────────────────────────────────────────────────


@mcp.tool
def search_prompts(query: str, limit: int = 10) -> str:
    """Search your prompt history by keyword.

    Returns matching prompts from past AI coding sessions.
    Useful for finding how you've previously asked about a topic.

    Args:
        query: Search term (case-insensitive substring match)
        limit: Maximum results to return (default 10)
    """
    db, _ = _get_db()
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


@mcp.tool
def get_prompt_library(category: str | None = None, limit: int = 20) -> str:
    """Get your reusable prompt patterns ranked by frequency.

    Shows high-frequency prompt patterns auto-categorized into:
    debug, implement, test, review, refactor, explain, config.

    Args:
        category: Filter by category (optional)
        limit: Maximum patterns to return (default 20)
    """
    db, _ = _get_db()
    patterns = db.get_patterns(category=category)
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
        return "No patterns yet. Run `reprompt scan` first."
    return json.dumps(items, indent=2)


@mcp.tool
def get_best_prompts(category: str = "implement", limit: int = 5) -> str:
    """Get your most effective prompts for a given category.

    Combines pattern frequency with effectiveness scoring to surface
    prompts that historically led to productive sessions.

    Args:
        category: Prompt category (debug/implement/test/review/refactor/explain/config)
        limit: Number of top prompts to return
    """
    db, _ = _get_db()
    patterns = db.get_patterns(category=category)
    # Sort by frequency as proxy for effectiveness
    top = sorted(patterns, key=lambda p: p.get("frequency", 0), reverse=True)[:limit]
    if not top:
        return f"No patterns in category '{category}' yet."
    items = [{"pattern": p["pattern_text"], "frequency": p["frequency"]} for p in top]
    return json.dumps(items, indent=2)


@mcp.tool
def get_trends(period: str = "7d", windows: int = 4) -> str:
    """Show how your prompting skills evolve over time.

    Returns per-period metrics: prompt count, average length,
    vocabulary size, and specificity score with trend deltas.

    Args:
        period: Time bucket size (7d, 14d, 30d)
        windows: Number of periods to compare (default 4)
    """
    from reprompt.core.trends import compute_trends

    db, _ = _get_db()
    data = compute_trends(db, period=period, n_windows=windows)
    return json.dumps(data, indent=2, default=str)


@mcp.tool
def get_status() -> str:
    """Show reprompt database statistics.

    Returns total prompts, unique count, sessions scanned, and patterns found.
    """
    db, _ = _get_db()
    stats = db.get_stats()
    return json.dumps(stats, indent=2)


@mcp.tool
def scan_sessions(source: str | None = None) -> str:
    """Scan AI coding sessions for new prompts.

    Scans session files, deduplicates, and stores unique prompts.
    Runs incrementally — only processes new sessions since last scan.

    Args:
        source: Specific source to scan (claude-code, openclaw). Scans all if omitted.
    """
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
