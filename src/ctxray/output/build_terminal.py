"""Rich terminal output for build command."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ctxray.core.scorer import tier_color

if TYPE_CHECKING:
    from ctxray.core.build import BuildResult


def render_build(result: BuildResult) -> str:
    """Render a build result as a Rich-formatted string."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True)

    # Score + tier header
    color = tier_color(result.score)
    console.print(f"\n  [{color}]{result.tier}[/{color}] · [{color}]{result.score:.0f}[/{color}]\n")

    # Built prompt panel
    console.print(Panel(result.prompt, title="Built Prompt", border_style="green"))

    # Components used
    if result.components_used:
        console.print(f"\n  [bold]Components[/bold] ({len(result.components_used)})")
        for comp in result.components_used:
            console.print(f"  [green]✓[/green] {comp}")

    # Suggestions for missing components
    if result.suggestions:
        console.print("\n  [bold]Add more[/bold]")
        for s in result.suggestions:
            console.print(f"  [yellow]→[/yellow] {s}")

    console.print()
    return buf.getvalue()
