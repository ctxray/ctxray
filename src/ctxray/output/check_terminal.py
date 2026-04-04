"""Rich terminal output for check command."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ctxray.core.scorer import tier_color

if TYPE_CHECKING:
    from ctxray.core.check import CheckResult


def render_check(result: CheckResult) -> str:
    """Render a full check result as a Rich-formatted string."""
    buf = StringIO()
    console = Console(file=buf, width=100, record=True)

    # Header: tier + score
    color = tier_color(result.total)
    console.print(
        f"\n  [{color}]{result.tier}[/{color}]"
        f" · [{color}]{result.total:.0f}[/{color}]"
        f"  [dim]({result.word_count} words, ~{result.token_count} tokens)[/dim]\n"
    )

    # Dimensions bar
    dims = [
        ("Clarity", result.clarity, 25),
        ("Context", result.context, 25),
        ("Position", result.position, 20),
        ("Structure", result.structure, 15),
        ("Repetition", result.repetition, 15),
    ]
    for name, val, max_val in dims:
        bar_len = int(val / max_val * 20) if max_val > 0 else 0
        bar = "█" * bar_len + "░" * (20 - bar_len)
        console.print(f"  {name:11s} [{_dim_color(val, max_val)}]{bar}[/] {val:.0f}/{max_val}")

    # Strengths
    if result.confirmations:
        console.print("\n  [bold]Strengths[/bold]")
        for c in result.confirmations:
            console.print(f"  [green]✓[/green] {c['message']}")

    # Suggestions
    if result.suggestions:
        console.print("\n  [bold]Improve[/bold]")
        for s in result.suggestions:
            pts = f" [dim](+{s['points']} pts)[/dim]" if s.get("points") else ""
            console.print(f"  [yellow]→[/yellow] {s['message']}{pts}")

    # Lint issues
    if result.lint_issues:
        console.print("\n  [bold]Lint[/bold]")
        for issue in result.lint_issues:
            prefix = (
                "[red]✗[/red]"
                if issue["severity"] == "error"
                else "[yellow]![/yellow]"
                if issue["severity"] == "warning"
                else "[dim]→[/dim]"
            )
            console.print(f"  {prefix} [{issue['rule']}] {issue['message']}")

    # Rewrite preview
    if result.rewrite_changes:
        delta = result.rewrite_delta
        if delta > 0:
            delta_str = f"[green]+{delta:.0f}[/green]"
        elif delta < 0:
            delta_str = f"[red]{delta:.0f}[/red]"
        else:
            delta_str = "[dim]±0[/dim]"
        console.print(f"\n  [bold]Auto-rewrite[/bold] ({delta_str} pts)")
        for change in result.rewrite_changes:
            console.print(f"  [green]✓[/green] {change}")
        console.print(Panel(result.rewritten, title="Rewritten", border_style="green", width=90))
    else:
        console.print("\n  [dim]No auto-rewrite improvements found.[/dim]")

    console.print()
    return buf.getvalue()


def _dim_color(val: float, max_val: float) -> str:
    pct = val / max_val if max_val > 0 else 0
    if pct >= 0.8:
        return "green"
    if pct >= 0.5:
        return "yellow"
    return "red"
