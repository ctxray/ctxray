"""Rich terminal output for projects command."""

from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _score_style(score: float | None) -> str:
    if score is None:
        return "dim"
    if score >= 80:
        return "bold green"
    if score >= 60:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


def render_projects_table(projects: list[dict[str, Any]]) -> str:
    """Render project quality summary as a Rich table."""
    buf = StringIO()
    console = Console(file=buf, width=110, record=True)

    if not projects:
        console.print("\n  [dim]No project data. Run [bold]ctxray scan[/bold] first.[/dim]\n")
        return buf.getvalue()

    # Header stats
    total_sessions = sum(p.get("session_count", 0) for p in projects)
    total_prompts = sum(p.get("prompt_count", 0) or 0 for p in projects)
    quality_scores = [p["avg_quality"] for p in projects if p.get("avg_quality") is not None]
    avg_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0

    console.print(
        Panel(
            f"  [bold]{len(projects)}[/bold] projects · "
            f"[bold]{total_sessions}[/bold] sessions · "
            f"[bold]{total_prompts}[/bold] prompts · "
            f"avg quality [bold]{avg_quality}[/bold]/100",
            title="[bold]Project Quality[/bold]",
            border_style="blue",
        )
    )

    # Table
    table = Table(show_header=True, header_style="bold", padding=(0, 1), expand=True)
    table.add_column("Project", style="bold", min_width=12)
    table.add_column("Sessions", justify="right", width=8)
    table.add_column("Prompts", justify="right", width=8)
    table.add_column("Quality", justify="right", width=8)
    table.add_column("Efficiency", justify="right", width=10)
    table.add_column("Focus", justify="right", width=7)
    table.add_column("Frustration", justify="right", width=11)
    table.add_column("Source", width=14)

    for p in projects:
        quality = p.get("avg_quality")
        efficiency = p.get("avg_efficiency")
        focus = p.get("avg_focus")

        abandon = p.get("abandonment_count", 0) or 0
        escalate = p.get("escalation_count", 0) or 0
        frustration_total = abandon + escalate
        sessions = p.get("session_count", 0)
        frust_pct = round(frustration_total / sessions * 100) if sessions > 0 else 0

        q_str = f"[{_score_style(quality)}]{quality:.0f}[/]" if quality else "[dim]--[/dim]"
        e_str = (
            f"[{_score_style(efficiency)}]{efficiency:.0f}[/]" if efficiency else "[dim]--[/dim]"
        )
        f_str = f"[{_score_style(focus)}]{focus:.0f}[/]" if focus else "[dim]--[/dim]"

        frust_style = "red" if frust_pct > 30 else "yellow" if frust_pct > 15 else "dim"
        frust_str = f"[{frust_style}]{frust_pct}%[/]" if frustration_total > 0 else "[dim]--[/dim]"

        sources = p.get("sources", "")
        # Shorten source names
        short_sources = (
            sources.replace("claude-code", "claude").replace("-ext", "") if sources else ""
        )

        table.add_row(
            p.get("project", "unknown"),
            str(sessions),
            str(p.get("prompt_count", 0) or 0),
            q_str,
            e_str,
            f_str,
            frust_str,
            short_sources,
        )

    console.print(table)
    console.print()
    return buf.getvalue()
