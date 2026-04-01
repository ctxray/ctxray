"""Rich terminal output for rewrite command."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from reprompt.core.rewrite import RewriteResult


def render_rewrite(result: RewriteResult) -> str:
    """Render a rewrite result as a Rich-formatted string."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True)

    # Score change header
    delta = result.score_delta
    if delta > 0:
        delta_str = f"[green]+{delta:.0f}[/green]"
    elif delta < 0:
        delta_str = f"[red]{delta:.0f}[/red]"
    else:
        delta_str = "[dim]±0[/dim]"

    before_color = _score_color(result.score_before)
    after_color = _score_color(result.score_after)

    console.print(
        f"\n  [{before_color}]{result.score_before:.0f}[/{before_color}]"
        f" → [{after_color}]{result.score_after:.0f}[/{after_color}]"
        f" ({delta_str})\n"
    )

    # Rewritten prompt
    if result.changes:
        console.print(Panel(result.rewritten, title="Rewritten", border_style="green"))
    else:
        console.print("[dim]No automated improvements found.[/dim]")

    # Changes applied
    if result.changes:
        console.print("\n  [bold]Changes[/bold]")
        for change in result.changes:
            console.print(f"  [green]✓[/green] {change}")

    # Manual suggestions
    if result.manual_suggestions:
        console.print("\n  [bold]You should also[/bold]")
        for s in result.manual_suggestions:
            console.print(f"  [yellow]→[/yellow] {s}")

    console.print()
    return buf.getvalue()


def _score_color(score: float) -> str:
    if score >= 85:
        return "bold magenta"
    if score >= 70:
        return "bold green"
    if score >= 55:
        return "bold yellow"
    if score >= 40:
        return "yellow"
    return "bold red"
