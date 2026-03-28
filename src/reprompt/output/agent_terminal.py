"""Rich terminal rendering for agent workflow analysis."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from reprompt.core.agent import AggregateAgentReport
from reprompt.core.effectiveness import effectiveness_stars


def _bar(count: int, max_count: int, width: int = 20) -> str:
    """Render a simple bar chart segment."""
    if max_count == 0:
        return ""
    filled = max(1, round(count / max_count * width))
    return "\u2588" * filled


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}min"


def render_agent_report(agg: AggregateAgentReport) -> str:
    """Render aggregate agent report as formatted terminal output."""
    console = Console(record=True, width=100, file=StringIO())

    if agg.sessions_analyzed == 0:
        console.print("[dim]No agent sessions found.[/dim]")
        console.print("Run [bold cyan]reprompt scan[/bold cyan] to import sessions first.")
        return console.export_text()

    # Determine source(s)
    sources = sorted({r.source for r in agg.sessions})
    source_str = ", ".join(sources) if sources else "all"

    # Header
    period = ""
    if agg.period_start and agg.period_end:
        start = agg.period_start[:10]
        end = agg.period_end[:10]
        period = f"  |  {start} \u2192 {end}" if start != end else f"  |  {start}"

    header = f"Sessions: {agg.sessions_analyzed}  |  Source: {source_str}{period}"
    console.print(Panel(header, title="Agent Report", border_style="cyan"))

    # Efficiency summary
    console.print()
    console.print("  [bold]Efficiency[/bold]")
    console.print("  \u2500" * 40)
    avg_dur = _fmt_duration(agg.avg_duration_seconds)
    productive_pct = f"{agg.productive_ratio * 100:.0f}%"
    console.print(
        f"  Avg turns: {agg.avg_turns_per_session:.0f}  |  "
        f"Avg duration: {avg_dur}  |  "
        f"Productive: {productive_pct}"
    )
    console.print(
        f"  Tool calls: {agg.total_tool_calls}  |  "
        f"Errors: {agg.total_errors}  |  "
        f"Error loops: {agg.total_error_loops}"
    )

    # Tool distribution
    if agg.tool_distribution:
        console.print()
        console.print("  [bold]Tool Distribution[/bold]")
        console.print("  \u2500" * 40)
        max_count = max(agg.tool_distribution.values()) if agg.tool_distribution else 1
        total_tools = sum(agg.tool_distribution.values())
        for name, count in agg.tool_distribution.items():
            bar = _bar(count, max_count)
            pct = f"{count / total_tools * 100:.0f}%" if total_tools else "0%"
            console.print(f"  {name:<10} {bar}  {count}  ({pct})")

    # Error loops
    if agg.error_loops:
        console.print()
        console.print("  [bold]Error Loops[/bold]")
        console.print("  \u2500" * 40)
        for i, loop in enumerate(agg.error_loops, 1):
            console.print(f"  {i}. {loop.description}")

    # Session breakdown
    if agg.sessions:
        console.print()
        console.print("  [bold]Session Breakdown[/bold]")
        console.print("  \u2500" * 40)

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Rating", width=5)
        table.add_column("Session")
        table.add_column("Turns", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Type")

        # Sort by productive ratio desc
        sorted_sessions = sorted(
            agg.sessions, key=lambda r: r.efficiency.productive_ratio, reverse=True
        )
        for r in sorted_sessions:
            eff = r.efficiency
            score = eff.productive_ratio * (1 - eff.errors / max(eff.total_turns, 1) * 0.5)
            stars = effectiveness_stars(min(score, 1.0))
            sid = r.session_id[:12]
            dur = _fmt_duration(eff.duration_seconds)
            stype = eff.session_type or ""
            table.add_row(stars, sid, str(eff.total_turns), str(eff.errors), dur, stype)

        console.print(table)

    console.print()
    return console.export_text()


def render_loops_only(agg: AggregateAgentReport) -> str:
    """Render only the error loops section."""
    console = Console(record=True, width=100, file=StringIO())

    if not agg.error_loops:
        console.print(
            f"[green]No error loops detected[/green] across {agg.sessions_analyzed} sessions."
        )
        return console.export_text()

    console.print(
        f"[bold]{len(agg.error_loops)} error loop(s)[/bold] "
        f"across {agg.sessions_analyzed} sessions:"
    )
    console.print()
    for i, loop in enumerate(agg.error_loops, 1):
        console.print(f"  {i}. {loop.description}")
        span = loop.end_turn - loop.start_turn + 1
        console.print(f"     Turns {loop.start_turn}\u2192{loop.end_turn} ({span} turns)")
    console.print()

    return console.export_text()
