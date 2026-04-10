"""Rich terminal output for check command.

Uses "Coach, not Judge" psychology — matching the PR comment design:
- Score ≥ 70 (celebrate): show score + tier + dimensions with numbers
- Score 50-69 (encourage): show tier (no score) + dimensions (no numbers)
- Score < 50 (coach): skip score/tier/dimensions, lead with suggestions + rewrite

Rationale: a raw "DRAFT · 29" triggers grading anxiety. The rewrite is what
actually helps — lead with that for low-scoring prompts.
Use --verbose to see full details at any score level.
"""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ctxray.core.scorer import tier_color

if TYPE_CHECKING:
    from ctxray.core.check import CheckResult


def render_check(result: CheckResult, *, verbose: bool = False) -> str:
    """Render a full check result as a Rich-formatted string.

    Display depth varies by score (unless verbose=True):
    - ≥70: celebrate — full score, tier, dimensions with numbers
    - 50-69: encourage — tier only, dimensions without numbers
    - <50: coach — no score/tier/dimensions, lead with suggestions + rewrite
    """
    buf = StringIO()
    console = Console(file=buf, width=100, record=True, force_terminal=True)

    score = result.total

    if verbose:
        # Verbose mode: always show everything
        _render_full(console, result)
    elif score >= 70:
        _render_celebrate(console, result)
    elif score >= 50:
        _render_encourage(console, result)
    else:
        _render_coach(console, result)

    console.print()
    return buf.getvalue()


def _render_celebrate(console: Console, result: CheckResult) -> None:
    """Score ≥ 70: full display — celebrate the achievement."""
    color = tier_color(result.total)
    console.print(
        f"\n  [{color}]{result.tier}[/{color}]"
        f" · [{color}]{result.total:.0f}[/{color}]"
        f"  [dim]({result.word_count} words, ~{result.token_count} tokens)[/dim]\n"
    )
    _render_threshold(console, result)
    _render_dimensions(console, result, show_numbers=True)
    _render_strengths(console, result)
    _render_suggestions(console, result)
    _render_lint(console, result)
    _render_rewrite(console, result)


def _render_encourage(console: Console, result: CheckResult) -> None:
    """Score 50-69: show tier (no number) + dimensions (no numbers)."""
    color = tier_color(result.total)
    console.print(
        f"\n  [{color}]{result.tier}[/{color}]"
        f"  [dim]({result.word_count} words, ~{result.token_count} tokens)[/dim]\n"
    )
    _render_threshold(console, result)
    _render_dimensions(console, result, show_numbers=False)
    _render_strengths(console, result)
    _render_suggestions(console, result)
    _render_lint(console, result)
    _render_rewrite(console, result)


def _render_coach(console: Console, result: CheckResult) -> None:
    """Score < 50: skip score/tier/dimensions, lead with actionable content."""
    console.print(f"\n  [dim]({result.word_count} words, ~{result.token_count} tokens)[/dim]\n")
    # Lead with threshold status and missing features
    _render_threshold(console, result)
    # Then suggestions — the most helpful part
    _render_suggestions(console, result)
    _render_lint(console, result)
    _render_rewrite(console, result)


def _render_full(console: Console, result: CheckResult) -> None:
    """Verbose mode: show everything regardless of score."""
    color = tier_color(result.total)
    console.print(
        f"\n  [{color}]{result.tier}[/{color}]"
        f" · [{color}]{result.total:.0f}[/{color}]"
        f"  [dim]({result.word_count} words, ~{result.token_count} tokens)[/dim]\n"
    )
    _render_dimensions(console, result, show_numbers=True)
    _render_strengths(console, result)
    _render_suggestions(console, result)
    _render_lint(console, result)
    _render_rewrite(console, result)


# ── Shared rendering components ──


def _render_threshold(console: Console, result: CheckResult) -> None:
    """Render threshold pass/fail indicator with missing features diagnostic."""
    if result.threshold_pass:
        console.print(f"  [green]PASS[/green] [dim]Quality threshold ({result.threshold})[/dim]")
    else:
        console.print(
            f"  [red]BELOW THRESHOLD[/red] [dim]Score {result.total:.0f} < {result.threshold}[/dim]"
        )
        if result.missing_features:
            console.print("  [bold]Add these to pass:[/bold]")
            for feat in result.missing_features[:4]:  # top 4 most impactful
                console.print(f"  [yellow]+[/yellow] {feat}")


def _render_dimensions(console: Console, result: CheckResult, *, show_numbers: bool) -> None:
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
        if show_numbers:
            console.print(f"  {name:11s} [{_dim_color(val, max_val)}]{bar}[/] {val:.0f}/{max_val}")
        else:
            console.print(f"  {name:11s} [{_dim_color(val, max_val)}]{bar}[/]")


def _render_strengths(console: Console, result: CheckResult) -> None:
    if result.confirmations:
        console.print("\n  [bold]Strengths[/bold]")
        for c in result.confirmations:
            console.print(f"  [green]✓[/green] {c['message']}")


def _render_suggestions(console: Console, result: CheckResult) -> None:
    if result.suggestions:
        console.print("\n  [bold]Improve[/bold]")
        for s in result.suggestions:
            pts = f" [dim](+{s['points']} pts)[/dim]" if s.get("points") else ""
            console.print(f"  [yellow]→[/yellow] {s['message']}{pts}")


def _render_lint(console: Console, result: CheckResult) -> None:
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


def _render_rewrite(console: Console, result: CheckResult) -> None:
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


def _dim_color(val: float, max_val: float) -> str:
    pct = val / max_val if max_val > 0 else 0
    if pct >= 0.8:
        return "green"
    if pct >= 0.5:
        return "yellow"
    return "red"
