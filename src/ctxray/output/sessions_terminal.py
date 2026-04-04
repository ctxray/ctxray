"""Rich terminal rendering for session quality metrics."""

from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _score_style(score: float | None) -> str:
    """Return Rich style string for a quality score."""
    if score is None:
        return "dim"
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    if score >= 40:
        return "dim"
    return "red"


def _fmt_score(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{score:.0f}"


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}min"


def _bar(value: float, width: int = 10) -> str:
    """Render a 0-100 value as a bar chart."""
    filled = max(0, min(width, round(value / 100 * width)))
    return "\u2588" * filled + "\u2591" * (width - filled)


def render_sessions_table(sessions: list[dict[str, Any]]) -> str:
    """Render session quality overview as formatted terminal output."""
    console = Console(record=True, width=100, file=StringIO())

    if not sessions:
        console.print("[dim]No sessions with quality scores found.[/dim]")
        console.print("Run [bold cyan]ctxray scan[/bold cyan] to import and score sessions.")
        return console.export_text()

    # Compute avg quality
    scored = [s for s in sessions if s.get("quality_score") is not None]
    avg_q = sum(s["quality_score"] for s in scored) / len(scored) if scored else 0

    # Header
    header = f"Sessions: {len(sessions)}  |  Scored: {len(scored)}  |  Avg Quality: {avg_q:.0f}/100"
    console.print(Panel(header, title="Session Quality", border_style="cyan"))

    # Table
    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Session", max_width=20)
    table.add_column("Score", justify="right", width=5)
    table.add_column("Type", width=6)
    table.add_column("Turns", justify="right", width=5)
    table.add_column("Errors", justify="right", width=6)
    table.add_column("Duration", justify="right", width=8)
    table.add_column("Insight", max_width=30)

    for s in sessions:
        score = s.get("quality_score")
        style = _score_style(score)
        sid = (s.get("session_id") or "")[:20]
        stype = (s.get("session_type") or "")[:6]
        turns = str(s.get("prompt_count") or "—")
        errors = str(s.get("error_count") or "0")
        duration = _fmt_duration(s.get("duration_seconds"))
        insight = s.get("quality_insight") or ""

        table.add_row(
            sid,
            f"[{style}]{_fmt_score(score)}[/{style}]",
            stype,
            turns,
            errors,
            duration,
            insight,
        )

    console.print(table)
    console.print()
    return console.export_text()


def render_session_detail(session: dict[str, Any]) -> str:
    """Render a single session's quality breakdown."""
    console = Console(record=True, width=100, file=StringIO())

    sid = session.get("session_id", "unknown")
    score = session.get("quality_score")
    style = _score_style(score)

    console.print(
        Panel(
            f"Session: {sid}  |  Score: [{style}]{_fmt_score(score)}/100[/{style}]",
            title="Session Detail",
            border_style="cyan",
        )
    )

    # Component scores
    console.print()
    console.print("  [bold]Quality Components[/bold]")
    console.print("  \u2500" * 50)

    components = [
        ("Prompt Quality", session.get("prompt_quality_score"), "30%"),
        ("Efficiency", session.get("efficiency_score"), "30%"),
        ("Focus", session.get("focus_score"), "20%"),
        ("Outcome", session.get("outcome_score"), "20%"),
    ]

    for name, val, weight in components:
        if val is not None:
            bar = _bar(val)
            cs = _score_style(val)
            console.print(f"  {name:<16} {bar}  [{cs}]{val:.0f}[/{cs}]  (weight: {weight})")
        else:
            console.print(f"  {name:<16} [dim]not available[/dim]  (weight: {weight})")

    # Frustration signals
    console.print()
    console.print("  [bold]Frustration Signals[/bold]")
    console.print("  \u2500" * 50)

    signals = []
    if session.get("has_abandonment"):
        signals.append("[red]Abandonment[/red] — session ended with unresolved errors")
    if session.get("has_escalation"):
        signals.append("[red]Escalation[/red] — errors increased through session")
    stalls = session.get("stall_turns", 0)
    if stalls > 0:
        signals.append(f"[yellow]Stall turns[/yellow] — {stalls} turns with no tool use")

    if signals:
        for sig in signals:
            console.print(f"  \u26a0 {sig}")
    else:
        console.print("  [green]None detected[/green]")

    # Session info
    console.print()
    console.print("  [bold]Session Info[/bold]")
    console.print("  \u2500" * 50)
    console.print(f"  Source: {session.get('source', '—')}")
    console.print(f"  Type: {session.get('session_type') or '—'}")
    console.print(f"  Duration: {_fmt_duration(session.get('duration_seconds'))}")
    console.print(f"  Prompts: {session.get('prompt_count', '—')}")
    console.print(f"  Errors: {session.get('error_count', 0)}")
    console.print(f"  Insight: {session.get('quality_insight') or '—'}")

    console.print()
    return console.export_text()
