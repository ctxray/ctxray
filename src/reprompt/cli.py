"""CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from reprompt import __version__

app = typer.Typer(
    name="reprompt",
    help="Discover, analyze, and evolve your best prompts from AI coding sessions.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"reprompt {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
) -> None:
    """reprompt -- Discover, analyze, and evolve your best prompts from AI coding sessions."""


@app.command()
def scan(
    source: str | None = typer.Option(None, help="Source adapter (claude-code, openclaw)"),
    path: str | None = typer.Option(None, help="Custom session path"),
) -> None:
    """Scan AI tool sessions for prompts."""
    from reprompt.config import Settings
    from reprompt.core.pipeline import run_scan

    settings = Settings()
    result = run_scan(source=source, path=path, settings=settings)

    console.print("[bold]Scan complete[/bold]")
    console.print(f"  Sessions scanned: {result.sessions_scanned}")
    console.print(f"  Prompts found:    {result.total_parsed}")
    console.print(f"  Unique:           {result.unique_after_dedup}")
    console.print(f"  Duplicates:       {result.duplicates}")
    console.print(f"  New stored:       {result.new_stored}")


@app.command()
def report(
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    top: int = typer.Option(20, help="Number of top terms to show"),
) -> None:
    """Generate analytics report."""
    from reprompt.config import Settings
    from reprompt.core.pipeline import build_report_data
    from reprompt.output.json_out import format_json_report
    from reprompt.output.terminal import render_report

    settings = Settings()
    data = build_report_data(settings=settings)

    if format == "json":
        print(format_json_report(data))
    else:
        console.print(render_report(data))


@app.command()
def library(
    category: str | None = typer.Option(None, help="Filter by category"),
    export: str | None = typer.Argument(None, help="Export to file path (Markdown)"),
) -> None:
    """Show or export your prompt library."""
    from reprompt.config import Settings
    from reprompt.output.markdown import export_library_markdown
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    patterns = db.get_patterns(category=category)

    if export:
        md = export_library_markdown(patterns)
        Path(export).write_text(md)
        console.print(f"Library exported to {export}")
    else:
        if not patterns:
            console.print("No patterns yet. Run [bold]reprompt scan[/bold] first.")
            return
        from rich.table import Table

        table = Table(title="Prompt Library")
        table.add_column("#", style="dim", width=4)
        table.add_column("Pattern", max_width=50)
        table.add_column("Uses", justify="right")
        table.add_column("Category")
        for i, p in enumerate(patterns, 1):
            table.add_row(
                str(i),
                (
                    str(p.get("pattern_text", ""))[:50] + "..."
                    if len(str(p.get("pattern_text", ""))) > 50
                    else str(p.get("pattern_text", ""))
                ),
                str(p.get("frequency", 0)),
                str(p.get("category", "")),
            )
        console.print(table)


@app.command()
def status() -> None:
    """Show database statistics."""
    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    stats = db.get_stats()

    console.print("[bold]reprompt status[/bold]")
    console.print(f"  Total prompts:    {stats.get('total_prompts', 0)}")
    console.print(f"  Unique prompts:   {stats.get('unique_prompts', 0)}")
    console.print(f"  Sessions:         {stats.get('sessions_processed', 0)}")
    console.print(f"  Patterns:         {stats.get('patterns', 0)}")
    console.print(f"  DB path:          {settings.db_path}")


@app.command()
def purge(
    older_than: str = typer.Option("90d", help="Delete prompts older than (e.g. 90d)"),
) -> None:
    """Clean up old data."""
    import re

    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    m = re.fullmatch(r"(\d+)d?", older_than.strip(), re.IGNORECASE)
    if not m:
        raise typer.BadParameter("Use format like '90d' or '30'")
    days = int(m.group(1))
    settings = Settings()
    db = PromptDB(settings.db_path)
    deleted = db.purge_old_prompts(days)
    console.print(f"Purged {deleted} prompts older than {days} days")


@app.command("install-hook")
def install_hook(
    source: str = typer.Option("claude-code", help="AI tool to install hook for"),
) -> None:
    """Install post-session hook for automatic scanning."""
    home = Path.home()

    if source == "claude-code":
        hooks_dir = home / ".claude" / "hooks"
        hook_path = hooks_dir / "reprompt-scan.sh"

        if hook_path.exists():
            console.print(f"Hook already exists at {hook_path}")
            return

        if not (home / ".claude").exists():
            console.print("[yellow]Claude Code not detected (~/.claude/ not found)[/yellow]")
            return

        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path.write_text("#!/bin/sh\nreprompt scan --source claude-code\n")
        hook_path.chmod(0o755)
        console.print(f"[green]Hook installed at {hook_path}[/green]")
        console.print("reprompt will automatically scan after Claude Code sessions.")
    else:
        console.print(f"[yellow]Hook installation for '{source}' not yet supported[/yellow]")
