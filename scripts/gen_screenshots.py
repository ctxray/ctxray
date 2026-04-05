"""Generate SVG screenshots of ctxray commands for marketing.

Renders directly via Rich Console to preserve colors in SVG export.
"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from ctxray.core.build import build_prompt
from ctxray.core.check import check_prompt
from ctxray.core.rewrite import rewrite_prompt
from ctxray.core.scorer import get_tier, tier_color

OUT = Path("docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)


def _dim_color(val: float, max_val: float) -> str:
    pct = val / max_val if max_val > 0 else 0
    if pct >= 0.8:
        return "green"
    if pct >= 0.5:
        return "yellow"
    return "red"


def render_check_to_console(console: Console, result) -> None:
    """Render check result directly to a recording console."""
    color = tier_color(result.total)
    console.print(
        f"\n  [{color}]{result.tier}[/{color}]"
        f" · [{color}]{result.total:.0f}[/{color}]"
        f"  [dim]({result.word_count} words, ~{result.token_count} tokens)[/dim]\n"
    )

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
        c = _dim_color(val, max_val)
        console.print(f"  {name:11s} [{c}]{bar}[/] {val:.0f}/{max_val}")

    if result.confirmations:
        console.print("\n  [bold]Strengths[/bold]")
        for c in result.confirmations:
            console.print(f"  [green]✓[/green] {c['message']}")

    if result.suggestions:
        console.print("\n  [bold]Improve[/bold]")
        for s in result.suggestions:
            pts = f" [dim](+{s['points']} pts)[/dim]" if s.get("points") else ""
            console.print(f"  [yellow]→[/yellow] {s['message']}{pts}")

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
        console.print(Panel(result.rewritten, title="Rewritten", border_style="green", width=80))


def render_rewrite_to_console(console: Console, result) -> None:
    """Render rewrite result directly to a recording console."""
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

    if result.changes:
        console.print(Panel(result.rewritten, title="Rewritten", border_style="green"))
    if result.changes:
        console.print("\n  [bold]Changes[/bold]")
        for change in result.changes:
            console.print(f"  [green]✓[/green] {change}")
    if result.manual_suggestions:
        console.print("\n  [bold]You should also[/bold]")
        for s in result.manual_suggestions:
            console.print(f"  [yellow]→[/yellow] {s}")
    console.print()


def render_build_to_console(console: Console, result) -> None:
    """Render build result directly to a recording console."""
    color = tier_color(result.score)
    console.print(f"\n  [{color}]{result.tier}[/{color}] · [{color}]{result.score:.0f}[/{color}]\n")
    console.print(Panel(result.prompt, title="Built Prompt", border_style="green"))
    if result.components_used:
        console.print(f"\n  [bold]Components[/bold] ({len(result.components_used)})")
        for comp in result.components_used:
            console.print(f"  [green]✓[/green] {comp}")
    if result.suggestions:
        console.print("\n  [bold]Add more[/bold]")
        for s in result.suggestions:
            console.print(f"  [yellow]→[/yellow] {s}")
    console.print()


def export(name: str, render_fn, title: str) -> None:
    console = Console(record=True, width=88, force_terminal=True)
    render_fn(console)
    svg = console.export_svg(title=title)
    path = OUT / f"{name}.svg"
    path.write_text(svg)
    print(f"  ✓ {path} ({path.stat().st_size // 1024}KB)")


# --- Generate ---

# 1. check — bad prompt
bad = check_prompt(
    "I was wondering if you could maybe help me fix the authentication "
    "middleware because it seems to be kind of broken when users try to "
    "log in with expired tokens"
)
export("check-bad", lambda c: render_check_to_console(c, bad), "ctxray check")

# 2. check — good prompt
good = check_prompt(
    "Fix the JWT token expiration handling in src/auth/middleware.ts. "
    "Error: TypeError: Cannot read property 'exp' of undefined at "
    "verifyToken line 42. Users get 401 errors after 1 hour sessions. "
    "Don't modify existing refresh token tests."
)
export("check-good", lambda c: render_check_to_console(c, good), "ctxray check")

# 3. rewrite
rw = rewrite_prompt(
    "I was wondering if you could maybe help me fix the authentication "
    "middleware because it seems to be kind of broken when users try to "
    "log in with expired tokens"
)
export("rewrite", lambda c: render_rewrite_to_console(c, rw), "ctxray rewrite")

# 4. build
built = build_prompt(
    "fix the JWT expiration bug",
    files=["src/auth/middleware.ts"],
    error="TypeError: Cannot read property 'exp' of undefined",
    constraints=["don't modify refresh token tests", "keep backward compatibility"],
)
export("build", lambda c: render_build_to_console(c, built), "ctxray build")

print(f"\nDone! {len(list(OUT.glob('*.svg')))} SVGs in {OUT}/")
