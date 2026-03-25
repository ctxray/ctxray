"""Rich terminal rendering for the dashboard (bare `reprompt` command)."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from reprompt.core.dashboard import DashboardData


def render_dashboard(data: DashboardData) -> str:
    """Render dashboard data as formatted terminal output.

    Two modes:
    - Zero state: show discovered AI tools + getting-started guidance.
    - Data state: stats summary + actionable suggestions.
    """
    console = Console(record=True, width=100, file=StringIO())

    if not data.has_data:
        return _render_zero_state(console, data)
    return _render_data_state(console, data)


def _render_zero_state(console: Console, data: DashboardData) -> str:
    """Render the zero-state dashboard (no data imported yet)."""
    console.print()
    console.print(
        Panel(
            "[bold]reprompt[/bold] -- prompt intelligence for AI coding tools",
            border_style="cyan",
        )
    )

    if data.discoveries:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Tool")
        table.add_column("Sessions", justify="right")
        table.add_column("Est. Turns", justify="right")

        for d in data.discoveries:
            table.add_row(
                d["adapter"],
                str(d["sessions"]),
                str(d.get("turns_estimate", "?")),
            )

        console.print()
        console.print("  [bold green]Discovered AI tools:[/bold green]")
        console.print(table)
        console.print()
        console.print("  Run [bold cyan]reprompt scan[/bold cyan] to import your prompts.")
    else:
        console.print()
        console.print("  No AI coding tools detected.")
        console.print("  Run [bold cyan]reprompt scan --help[/bold cyan] to get started.")

    console.print()
    return console.export_text()


def _render_data_state(console: Console, data: DashboardData) -> str:
    """Render the data-state dashboard (has imported prompts)."""
    console.print()

    # Stats header
    overall = data.avg_score.get("overall", 0)
    comp_pct = f"{data.avg_compressibility * 100:.0f}%"

    stats_lines = [
        f"  [bold]Prompts (7d):[/bold]  {data.prompt_count}",
        f"  [bold]Sessions:[/bold]      {data.session_count}",
        f"  [bold]Avg Score:[/bold]     {overall}/100",
        f"  [bold]Compressibility:[/bold] {comp_pct}",
    ]

    if data.long_sessions > 0:
        stats_lines.append(f"  [bold]Long Sessions:[/bold] {data.long_sessions} (60+ turns)")

    console.print(Panel("\n".join(stats_lines), title="reprompt", border_style="cyan"))

    # Per-task-type scores
    task_scores = {k: v for k, v in data.avg_score.items() if k != "overall"}
    if task_scores:
        console.print("  [dim]Scores by task type:[/dim]")
        for task, score in sorted(task_scores.items()):
            console.print(f"    {task}: {score}/100")
        console.print()

    # Suggestions
    console.print("  [bold]Next steps:[/bold]")
    if data.long_sessions > 0:
        console.print("    [cyan]reprompt distill[/cyan]  -- extract key turns from long sessions")
    else:
        console.print("    [cyan]reprompt distill[/cyan]  -- extract key turns from conversations")
    console.print("    [cyan]reprompt insights[/cyan] -- compare your patterns to research-optimal")
    console.print("    [cyan]reprompt compress[/cyan] -- optimize prompts for fewer tokens")

    console.print()
    return console.export_text()
