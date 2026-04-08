"""Rich terminal output for explain command."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ctxray.core.scorer import tier_color

if TYPE_CHECKING:
    from ctxray.core.explain import ExplainResult


def render_explain(result: ExplainResult) -> str:
    """Render an explain result as a Rich-formatted string."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True, force_terminal=True)

    # Header
    color = tier_color(result.score)
    console.print(f"\n  [{color}]{result.tier}[/{color}] · [{color}]{result.score:.0f}[/{color}]\n")

    # Summary
    console.print(Panel(result.summary, title="Analysis", border_style="blue"))

    # Strengths
    if result.strengths:
        console.print("\n  [bold green]What's working[/bold green]")
        for s in result.strengths:
            console.print(f"  [green]✓[/green] {s}")

    # Weaknesses
    if result.weaknesses:
        console.print("\n  [bold yellow]What's missing[/bold yellow]")
        for w in result.weaknesses:
            console.print(f"  [yellow]![/yellow] {w}")

    # Tips
    if result.tips:
        console.print("\n  [bold]How to improve[/bold]")
        for t in result.tips:
            console.print(f"  [cyan]→[/cyan] {t}")

    console.print()
    return buf.getvalue()
