"""Rich terminal output for rewrite command."""

from __future__ import annotations

import difflib
from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ctxray.core.scorer import get_tier, tier_color

if TYPE_CHECKING:
    from ctxray.core.rewrite import RewriteResult


def render_rewrite(result: RewriteResult) -> str:
    """Render a rewrite result as a Rich-formatted string."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True, force_terminal=True)

    # Score change header — tier-first display
    delta = result.score_delta
    if delta > 0:
        delta_str = f"[green]+{delta:.0f}[/green]"
    elif delta < 0:
        delta_str = f"[red]{delta:.0f}[/red]"
    else:
        delta_str = "[dim]±0[/dim]"

    before_color = tier_color(result.score_before)
    after_color = tier_color(result.score_after)
    before_tier = get_tier(result.score_before)
    after_tier = get_tier(result.score_after)

    console.print(
        f"\n  [{before_color}]{before_tier} · {result.score_before:.0f}[/{before_color}]"
        f" → [{after_color}]{after_tier} · {result.score_after:.0f}[/{after_color}]"
        f"  ({delta_str} pts)\n"
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


def render_rewrite_diff(result: RewriteResult) -> str:
    """Render a unified diff between original and rewritten prompt."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True, force_terminal=True)

    orig_lines = result.original.splitlines(keepends=True)
    new_lines = result.rewritten.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines, new_lines, fromfile="original", tofile="rewritten", lineterm=""
    )

    console.print()
    has_diff = False
    for line in diff:
        line = line.rstrip("\n")
        if line.startswith("---"):
            console.print(f"[bold red]{line}[/bold red]")
            has_diff = True
        elif line.startswith("+++"):
            console.print(f"[bold green]{line}[/bold green]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/cyan]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/green]")
        else:
            console.print(f" {line}")

    if not has_diff:
        console.print("[dim]No changes — prompt is already optimized.[/dim]")

    # Score summary
    delta = result.score_delta
    if delta > 0:
        delta_str = f"[green]+{delta:.0f}[/green]"
    elif delta < 0:
        delta_str = f"[red]{delta:.0f}[/red]"
    else:
        delta_str = "[dim]±0[/dim]"
    before_tier = get_tier(result.score_before)
    after_tier = get_tier(result.score_after)
    before_c = tier_color(result.score_before)
    after_c = tier_color(result.score_after)
    console.print(
        f"\n  [{before_c}]{before_tier} · {result.score_before:.0f}[/{before_c}]"
        f" → [{after_c}]{after_tier} · {result.score_after:.0f}[/{after_c}]"
        f"  ({delta_str} pts)"
    )
    console.print()
    return buf.getvalue()
