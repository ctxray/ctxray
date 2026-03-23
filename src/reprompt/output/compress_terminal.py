"""Rich terminal rendering for compress results."""

from __future__ import annotations

from rich.console import Console

from reprompt.core.compress import CompressResult


def render_compress(result: CompressResult) -> str:
    """Render a compress result as formatted terminal output."""
    from io import StringIO

    console = Console(record=True, width=100, file=StringIO())

    console.print()

    # Original
    console.print(f"  [dim]Original:[/dim]    {result.original[:200]}")

    # Compressed
    console.print(f"  [bold green]Compressed:[/bold green]  {result.compressed[:200]}")

    console.print()

    # Token savings
    if result.original_tokens > 0:
        pct = f"{result.savings_pct:.0f}%"
        console.print(
            f"  [dim]Tokens:[/dim]  {result.original_tokens} → {result.compressed_tokens}  "
            f"[bold cyan]({pct} saved)[/bold cyan]"
        )
    else:
        console.print("  [dim]Tokens:[/dim]  0 → 0  (no change)")

    # Changes
    if result.changes:
        changes_str = ", ".join(result.changes)
        console.print(f"  [dim]Changes:[/dim] {changes_str}")

    console.print()

    return console.export_text()
