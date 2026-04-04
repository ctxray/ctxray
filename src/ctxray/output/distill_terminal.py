"""Rich terminal rendering for distill results."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel

from ctxray.core.conversation import DistillResult


def _importance_stars(importance: float) -> str:
    """Convert importance score to star rating."""
    if importance >= 0.7:
        return "[bold yellow]\u2605\u2605\u2605[/bold yellow]"
    elif importance >= 0.5:
        return "[yellow]\u2605\u2605[/yellow][dim]\u2606[/dim]"
    else:
        return "[dim]\u2605\u2606\u2606[/dim]"


def render_distill(result: DistillResult) -> str:
    """Render a distill result as formatted terminal output (Tier 1: filtered)."""
    console = Console(record=True, width=100, file=StringIO())

    conv = result.conversation
    stats = result.stats

    # Header
    duration_str = ""
    if stats.total_duration_seconds > 0:
        mins = stats.total_duration_seconds // 60
        duration_str = f" | {mins}min"

    project_str = f" | {conv.project}" if conv.project else ""

    detected_type = getattr(conv, "_detected_type", None)
    type_str = f" | {detected_type.value} session" if detected_type is not None else ""

    header = (
        f"session {conv.session_id[:12]} ({conv.source})\n"
        f"  {stats.total_turns} \u2192 {stats.kept_turns} turns"
        f"{project_str}{duration_str}{type_str}"
    )
    console.print(Panel(header, title="Distill", border_style="cyan"))

    if not result.filtered_turns:
        console.print(f"  [dim]No key turns found above threshold {result.threshold}[/dim]")
        console.print()
        return console.export_text()

    # Render turn pairs
    i = 0
    while i < len(result.filtered_turns):
        turn = result.filtered_turns[i]

        if turn.role == "user":
            stars = _importance_stars(turn.importance)
            console.print(f"\n  {stars} [bold]\\[T{turn.turn_index}][/bold] User:")
            console.print(f"    {turn.text[:200]}")

            # Check if next turn is paired assistant
            if (
                i + 1 < len(result.filtered_turns)
                and result.filtered_turns[i + 1].role == "assistant"
            ):
                asst = result.filtered_turns[i + 1]
                asst_text = asst.text[:80] + "..." if len(asst.text) > 80 else asst.text
                console.print(f"    [dim]Assistant: {asst_text}[/dim]")
                i += 1
        else:
            console.print(f"\n  [dim]\\[T{turn.turn_index}] Assistant: {turn.text[:80]}[/dim]")

        i += 1

    console.print()

    # Files changed
    if result.files_changed:
        files = ", ".join(result.files_changed[:10])
        console.print(f"  [dim]Files changed:[/dim] {files}")
        console.print()

    return console.export_text()


def render_distill_summary(result: DistillResult) -> str:
    """Render a distill result as summary output (Tier 2)."""
    console = Console(record=True, width=100, file=StringIO())

    if result.summary:
        console.print(Panel(result.summary, title="Session Summary", border_style="cyan"))
    else:
        console.print("[dim]No summary available.[/dim]")

    return console.export_text()
