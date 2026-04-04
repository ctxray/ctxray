"""Rich terminal rendering for compress results."""

from __future__ import annotations

from rich.console import Console

from ctxray.core.compress import CompressResult


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

    # Token savings — framed as quality improvement (Zhang+ 2505.00019)
    if result.original_tokens > 0:
        pct = f"{result.savings_pct:.0f}%"
        console.print(
            f"  [dim]Tokens:[/dim]  {result.original_tokens} → {result.compressed_tokens}  "
            f"[bold cyan]({pct} saved)[/bold cyan]"
        )
        if 5 <= result.savings_pct <= 50:
            console.print(
                "  [dim]Research:[/dim] Moderate compression improves LLM output quality "
                "[dim](Zhang+ 2505.00019)[/dim]"
            )
    else:
        console.print("  [dim]Tokens:[/dim]  0 → 0  (no change)")

    # Changes
    if result.changes:
        changes_str = ", ".join(result.changes)
        console.print(f"  [dim]Changes:[/dim] {changes_str}")

    console.print()

    return console.export_text()
