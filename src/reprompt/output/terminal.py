"""Rich terminal report output."""

from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def render_report(data: dict[str, Any]) -> str:
    """Render a full report to a string using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    # Title
    console.print("\n[bold]reprompt — AI Session Analytics[/bold]")
    console.print("=" * 40)

    # Overview panel
    ov = data["overview"]
    overview_text = (
        f"Total prompts:     {ov['total_prompts']}\n"
        f"Unique (deduped):  {ov['unique_prompts']}\n"
        f"Sessions scanned:  {ov['sessions_scanned']}\n"
        f"Sources:           {', '.join(ov['sources']) or 'none'}\n"
        f"Date range:        {ov['date_range'][0]} → {ov['date_range'][1]}"
    )
    console.print(Panel(overview_text, title="Overview"))

    # Top patterns table
    if data["top_patterns"]:
        table = Table(title="Top Prompt Patterns")
        table.add_column("#", style="dim", width=4)
        table.add_column("Pattern", max_width=40)
        table.add_column("Count", justify="right")
        table.add_column("Category")
        for i, p in enumerate(data["top_patterns"][:10], 1):
            table.add_row(str(i), p["pattern_text"][:40], str(p["frequency"]), p["category"])
        console.print(table)

    # Projects bar chart
    if data["projects"]:
        console.print("\n[bold]Activity by Project[/bold]")
        max_val = max(data["projects"].values()) if data["projects"] else 1
        for name, count in sorted(data["projects"].items(), key=lambda x: -x[1]):
            bar_len = int(count / max_val * 20)
            bar = "\u2588" * bar_len
            console.print(f"  {name:<20} {bar} {count}")

    # Categories
    if data["categories"]:
        console.print("\n[bold]Prompt Categories[/bold]")
        total = sum(data["categories"].values()) or 1
        for cat, count in sorted(data["categories"].items(), key=lambda x: -x[1]):
            pct = int(count / total * 100)
            bar_len = int(count / total * 20)
            bar = "\u2588" * bar_len
            console.print(f"  {cat:<12} {bar} {pct}%")

    console.print("\nRun `reprompt library` to see your reusable prompt collection")

    return buf.getvalue()
