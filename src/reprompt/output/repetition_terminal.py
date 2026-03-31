"""Rich terminal rendering for cross-session repetition analysis."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from reprompt.core.repetition import RepetitionReport


def render_repetition_report(report: RepetitionReport) -> str:
    """Render repetition report as formatted terminal output."""
    console = Console(record=True, width=100, file=StringIO())

    if not report.recurring_topics:
        console.print("[dim]No cross-session repetition detected.[/dim]")
        console.print(
            "This means your prompts across sessions are unique — no recurring patterns found."
        )
        return console.export_text()

    rate_pct = f"{report.repetition_rate * 100:.0f}%"
    header = (
        f"Prompts: {report.total_prompts_analyzed}  |  "
        f"Sessions: {report.total_sessions}  |  "
        f"Repetition Rate: {rate_pct}"
    )
    console.print(Panel(header, title="Cross-Session Repetition", border_style="cyan"))

    # Table of recurring topics
    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Topic", max_width=45)
    table.add_column("Sessions", justify="right", width=8)
    table.add_column("Matches", justify="right", width=7)
    table.add_column("Range", max_width=25)

    for topic in report.recurring_topics[:10]:
        text = topic.canonical_text
        if len(text) > 45:
            text = text[:42] + "..."

        date_range = ""
        if topic.earliest and topic.latest:
            start = topic.earliest[:10]
            end = topic.latest[:10]
            date_range = f"{start} \u2192 {end}" if start != end else start

        table.add_row(
            text,
            str(topic.session_count),
            str(topic.total_matches),
            date_range,
        )

    console.print(table)
    console.print()

    return console.export_text()
