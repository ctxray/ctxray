"""Rich terminal renderer for Wrapped-style prompt DNA reports."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ctxray.core.wrapped import WrappedReport

# Maximum points per scoring category.
_CATEGORY_MAX: dict[str, float] = {
    "structure": 25.0,
    "context": 25.0,
    "position": 20.0,
    "repetition": 15.0,
    "clarity": 15.0,
}

# Display names (title-cased) for each category.
_CATEGORY_LABELS: dict[str, str] = {
    "structure": "Structure",
    "context": "Context",
    "position": "Position",
    "repetition": "Repetition",
    "clarity": "Clarity",
}

_BAR_WIDTH = 20  # number of characters for percentage bar


def _pct_bar(score: float, max_score: float) -> str:
    """Return a Rich-compatible percentage bar string."""
    if max_score <= 0:
        return " " * _BAR_WIDTH + "  0%"
    pct = min(score / max_score, 1.0)
    filled = round(pct * _BAR_WIDTH)
    empty = _BAR_WIDTH - filled
    bar = "\u2588" * filled + "\u2591" * empty
    return f"{bar} {pct * 100:4.0f}%"


def render_wrapped(report: WrappedReport) -> str:
    """Render a Wrapped report to a Rich terminal string."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=60)

    # --- Header panel ---
    console.print()
    console.print(
        Panel(
            "[bold magenta]Prompt DNA Report[/bold magenta]",
            border_style="magenta",
        )
    )

    # --- Early return if no scored prompts ---
    if report.scored_prompts == 0:
        console.print()
        console.print(
            "[yellow]No scored prompts found.[/yellow]\n"
            "Run [bold]ctxray scan[/bold] first to analyze your prompts."
        )
        console.print()
        return buf.getvalue()

    # --- Persona ---
    console.print()
    persona = report.persona
    console.print(
        f"{persona.emoji}  [bold]{persona.name.title()}[/bold]  [dim]{persona.description}[/dim]"
    )

    # --- Stats ---
    console.print()
    stats_text = (
        f"Total prompts:    {report.total_prompts}\n"
        f"Average score:    {report.avg_overall:.1f} / 100\n"
        f"Top score:        {report.top_score:.1f}\n"
        f"Top task type:    {report.top_task_type}"
    )
    console.print(Panel(stats_text, title="Stats", border_style="cyan"))

    # --- Score breakdown bars ---
    console.print()
    breakdown_table = Table(
        title="Score Breakdown",
        show_header=True,
        header_style="bold",
        border_style="blue",
        width=58,
    )
    breakdown_table.add_column("Category", min_width=12)
    breakdown_table.add_column("Score", justify="right", min_width=8)
    breakdown_table.add_column("Bar", min_width=28)

    for key in ("structure", "context", "position", "repetition", "clarity"):
        score = report.avg_scores.get(key, 0.0)
        max_val = _CATEGORY_MAX[key]
        label = _CATEGORY_LABELS[key]
        bar = _pct_bar(score, max_val)
        breakdown_table.add_row(label, f"{score:.1f}/{max_val:.0f}", bar)

    console.print(breakdown_table)

    # --- Persona traits (top 3) ---
    if persona.traits:
        console.print()
        traits_text = Text()
        for i, trait in enumerate(persona.traits[:3]):
            if i > 0:
                traits_text.append("\n")
            traits_text.append(f"  {i + 1}. {trait}")
        console.print(Panel(traits_text, title="Your Traits", border_style="green"))

    # --- Task distribution (top 3 by count) ---
    if report.task_distribution:
        console.print()
        sorted_tasks = sorted(report.task_distribution.items(), key=lambda x: x[1], reverse=True)
        task_table = Table(
            title="Task Distribution",
            show_header=True,
            header_style="bold",
            border_style="yellow",
        )
        task_table.add_column("Task Type", min_width=14)
        task_table.add_column("Count", justify="right")
        for task_type, count in sorted_tasks[:3]:
            task_table.add_row(task_type, str(count))
        console.print(task_table)

    console.print()
    return buf.getvalue()
