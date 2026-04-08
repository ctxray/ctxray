"""Rich terminal rendering for `ctxray tools` command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.table import Table

from ctxray.core.tools_comparison import ToolComparison


def _score_style(score: float) -> str:
    if score >= 70:
        return "bold green"
    if score >= 55:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


def render_tool_comparison(comparison: ToolComparison) -> str:
    """Render side-by-side tool comparison with insights."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True, force_terminal=True)

    if not comparison.tools:
        console.print("\n  [dim]No tool data yet. Run [bold]ctxray scan[/bold] first.[/dim]\n")
        return buf.getvalue()

    console.print()
    console.print(f"  [bold]Cross-tool comparison[/bold] · {len(comparison.tools)} AI tools")
    console.print()

    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Tool", style="cyan")
    table.add_column("Prompts", justify="right")
    table.add_column("Avg Words", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("Top Task")
    table.add_column("File Refs", justify="right")
    table.add_column("Error Ctx", justify="right")

    for t in comparison.tools:
        score_color = _score_style(t.avg_score)
        table.add_row(
            t.source,
            str(t.prompt_count),
            f"{t.avg_words:.0f}",
            f"[{score_color}]{t.avg_score:.0f}[/{score_color}]",
            t.top_task_type,
            f"{t.file_ref_rate * 100:.0f}%",
            f"{t.error_context_rate * 100:.0f}%" if t.error_context_rate > 0 else "-",
        )

    console.print(table)

    if comparison.insights:
        console.print()
        console.print("  [bold]Findings[/bold]")
        for insight in comparison.insights:
            console.print(f"  [yellow]→[/yellow] {insight}")
        console.print()
    else:
        console.print()

    return buf.getvalue()
