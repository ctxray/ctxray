"""Rich terminal rendering for personal prompt patterns."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.table import Table

from ctxray.core.patterns import PatternsReport


def render_patterns(report: PatternsReport) -> str:
    """Render a PatternsReport as formatted terminal output."""
    console = Console(record=True, width=100, file=StringIO())

    if report.total_analyzed == 0:
        console.print(
            "\n  [dim]No scored prompts found. Run [bold]ctxray scan[/bold] first.[/dim]\n"
        )
        return console.export_text()

    console.print()

    # Header
    analyzed = report.total_analyzed
    console.print(
        f"  [bold]Personal Prompt Patterns[/bold]  [dim]({analyzed} prompts analyzed)[/dim]"
    )
    console.print()

    # Task distribution bar
    total = report.total_analyzed
    for task, count in sorted(report.task_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = count / total * 100
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        console.print(f"  [dim]{task:<12}[/dim] [cyan]{bar}[/cyan] {count} ({pct:.0f}%)")

    console.print()

    # Per-task patterns
    for pattern in report.patterns:
        if not pattern.gaps:
            continue

        tt = pattern.task_type
        cnt = pattern.count
        avg = pattern.avg_score
        console.print(f"  [bold]{tt}[/bold] prompts  [dim]({cnt} total, avg score {avg})[/dim]")

        for gap in pattern.gaps:
            pct = int(gap.missing_rate * 100)
            color = "red" if gap.impact == "high" else "yellow" if gap.impact == "medium" else "dim"
            console.print(
                f"    [{color}]{pct}% missing {gap.label}[/{color}]  [dim]→ {gap.suggestion}[/dim]"
            )

        console.print()

    # Top gaps summary
    if report.top_gaps:
        console.print("  [bold]Your most common gaps[/bold]")
        table = Table(show_header=True, header_style="dim", box=None, padding=(0, 2))
        table.add_column("Gap", style="bold")
        table.add_column("Missing", justify="right")
        table.add_column("Fix", style="dim")

        for gap in report.top_gaps:
            pct = f"{int(gap.missing_rate * 100)}%"
            table.add_row(gap.label, pct, gap.suggestion)

        console.print(table)
        console.print()

    return console.export_text()
