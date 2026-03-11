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
        print(render_report(data), end="")


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
def search(
    query: str = typer.Argument(..., help="Search term (case-insensitive)"),
    limit: int = typer.Option(20, help="Maximum results to show"),
) -> None:
    """Search your prompt history by keyword."""
    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    results = db.search_prompts(query, limit=limit)

    if not results:
        console.print(f"No prompts matching [bold]{query}[/bold]")
        return

    from rich.table import Table

    table = Table(title=f"Search: '{query}' ({len(results)} results)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Prompt", max_width=60)
    table.add_column("Source")
    table.add_column("Date", width=10)
    for i, p in enumerate(results, 1):
        text = p.get("text", "")
        display = text[:60] + "..." if len(text) > 60 else text
        ts = p.get("timestamp", "")[:10]
        table.add_row(str(i), display, p.get("source", ""), ts)
    console.print(table)


@app.command()
def trends(
    period: str = typer.Option("7d", help="Time bucket size: 7d, 14d, 30d, 1m"),
    windows: int = typer.Option(4, help="Number of periods to compare"),
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
) -> None:
    """Show how your prompting evolves over time."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.trends import compute_trends
    from reprompt.output.terminal import render_trends
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    data = compute_trends(db, period=period, n_windows=windows)

    if format == "json":
        print(json_mod.dumps(data, indent=2, default=str))
    else:
        print(render_trends(data), end="")


@app.command()
def effectiveness(
    top: int = typer.Option(10, help="Show top N patterns by effectiveness"),
    worst: int = typer.Option(3, help="Show bottom N patterns"),
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
) -> None:
    """Show prompt pattern effectiveness scores."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.effectiveness import effectiveness_stars
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    summary = db.get_effectiveness_summary()
    sessions = db.get_session_meta(limit=100)

    if format == "json":
        print(json_mod.dumps({"summary": summary, "sessions": sessions}, indent=2, default=str))
        return

    if not sessions:
        console.print("No effectiveness data yet. Run [bold]reprompt scan[/bold] first.")
        return

    from rich.table import Table

    console.print("\n[bold]reprompt effectiveness — Session Quality[/bold]")
    console.print("=" * 40)

    avg = summary.get("avg_score", 0) or 0
    console.print(
        f"  Sessions analyzed: {summary.get('total', 0)}  |  "
        f"Avg score: {avg:.2f} {effectiveness_stars(avg)}"
    )

    table = Table(title=f"Top {top} Sessions by Effectiveness")
    table.add_column("#", style="dim", width=4)
    table.add_column("Session", max_width=30)
    table.add_column("Project", max_width=15)
    table.add_column("Score", justify="right")
    table.add_column("Rating")
    table.add_column("Status")

    for i, s in enumerate(sessions[:top], 1):
        score = s.get("effectiveness_score", 0) or 0
        table.add_row(
            str(i),
            str(s.get("session_id", ""))[:30],
            str(s.get("project", ""))[:15],
            f"{score:.2f}",
            effectiveness_stars(score),
            str(s.get("final_status", "")),
        )
    console.print(table)

    if worst > 0 and len(sessions) > top:
        worst_sessions = sorted(sessions, key=lambda x: x.get("effectiveness_score", 0) or 0)
        table2 = Table(title=f"Bottom {worst} (Patterns to Improve)")
        table2.add_column("#", style="dim", width=4)
        table2.add_column("Session", max_width=30)
        table2.add_column("Score", justify="right")
        table2.add_column("Status")
        for i, s in enumerate(worst_sessions[:worst], 1):
            score = s.get("effectiveness_score", 0) or 0
            table2.add_row(
                str(i),
                str(s.get("session_id", ""))[:30],
                f"{score:.2f}",
                str(s.get("final_status", "")),
            )
        console.print(table2)


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


@app.command("mcp-serve")
def mcp_serve() -> None:
    """Start MCP server (stdio transport) for Claude Code / Continue.dev / Zed."""
    try:
        from reprompt.mcp import run_server
    except ImportError:
        console.print(
            "[red]MCP support requires fastmcp.[/red]\n"
            "Install with: [bold]pip install reprompt-cli\\[mcp][/bold]"
        )
        raise typer.Exit(1)
    run_server()


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


@app.command()
def demo() -> None:
    """Run reprompt on demo data to see what it looks like."""
    import shutil
    import tempfile

    from reprompt.config import Settings
    from reprompt.core.pipeline import build_report_data, run_scan
    from reprompt.demo import generate_demo_sessions
    from reprompt.output.terminal import render_report

    tmp = Path(tempfile.mkdtemp(prefix="reprompt-demo-"))
    sessions_dir = tmp / "sessions"
    db_path = tmp / "demo.db"

    try:
        console.print("[bold]Generating demo data...[/bold]")
        n = generate_demo_sessions(sessions_dir)
        console.print(f"  Generated {n} prompts across 6 weeks\n")

        settings = Settings(db_path=db_path)
        result = run_scan(source="claude-code", path=str(sessions_dir), settings=settings)

        console.print("[bold]Scan complete[/bold]")
        console.print(f"  Sessions: {result.sessions_scanned}")
        console.print(f"  Prompts:  {result.total_parsed}")
        console.print(f"  Unique:   {result.unique_after_dedup}")
        console.print(f"  Dupes:    {result.duplicates}\n")

        data = build_report_data(settings=settings)
        print(render_report(data), end="")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.command("install-hook")
def install_hook(
    source: str = typer.Option("claude-code", help="AI tool to install hook for"),
) -> None:
    """Install post-session hook for automatic scanning."""
    home = Path.home()

    if source == "claude-code":
        claude_dir = home / ".claude"
        if not claude_dir.exists():
            console.print("[yellow]Claude Code not detected (~/.claude/ not found)[/yellow]")
            return

        settings_path = claude_dir / "settings.json"
        hook_command = "reprompt scan --source claude-code"
        hook_entry = {"type": "command", "command": hook_command}

        # Load existing settings or start fresh
        if settings_path.exists():
            import json

            settings_data = json.loads(settings_path.read_text())
        else:
            settings_data = {}

        # Ensure hooks.Stop exists
        hooks = settings_data.setdefault("hooks", {})
        stop_hooks = hooks.setdefault("Stop", [])

        # Check if already registered
        for h in stop_hooks:
            if isinstance(h, dict) and h.get("command") == hook_command:
                console.print("Hook already registered in Claude Code settings.")
                return

        stop_hooks.append(hook_entry)

        import json

        settings_path.write_text(json.dumps(settings_data, indent=2) + "\n")
        console.print("[green]Hook registered in ~/.claude/settings.json[/green]")
        console.print("reprompt will automatically scan when Claude Code sessions end.")
    else:
        console.print(f"[yellow]Hook installation for '{source}' not yet supported[/yellow]")
