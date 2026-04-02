"""CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from reprompt import __version__

if TYPE_CHECKING:
    from reprompt.core.conversation import Conversation
    from reprompt.storage.db import PromptDB


def _resolve_text(text: str, file: str) -> str:
    """Resolve prompt text from argument or --file option."""
    if file:
        p = Path(file)
        if not p.is_file():
            typer.echo(f"Error: file not found: {file}", err=True)
            raise typer.Exit(1)
        return p.read_text(encoding="utf-8").strip()
    if text == "-":
        import sys

        return sys.stdin.read().strip()
    return text


def _copy_to_clip(text: str, quiet: bool = False) -> None:
    """Copy text to clipboard with user feedback."""
    from reprompt.sharing.clipboard import copy_to_clipboard

    if copy_to_clipboard(text):
        if not quiet:
            typer.echo("  Copied to clipboard!")
    else:
        typer.echo("  Could not copy to clipboard (xclip/xsel not found)", err=True)


app = typer.Typer(
    name="reprompt",
    help="Discover, analyze, and evolve your best prompts from AI coding sessions.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    epilog=(
        "Quick start:\n\n"
        "  reprompt scan            Discover prompts from your AI tools\n\n"
        "  reprompt                 See your dashboard\n\n"
        '  reprompt score "prompt"  Score any prompt instantly'
    ),
)
console = Console()


def _show_hint(db: object, command: str, *, json_output: bool = False) -> None:
    """Show journey hint or one-time feedback hint after a command."""
    if json_output:
        return
    from reprompt.core.suggestions import get_suggestion, maybe_feedback_hint

    fb = maybe_feedback_hint(db, command)
    if fb:
        console.print(f"  [dim]\u2192 {fb}[/dim]\n")
        return
    hint = get_suggestion(command)
    if hint:
        console.print(f"  [dim]\u2192 Try: {hint}[/dim]\n")


# --- Template sub-app ---
template_app = typer.Typer(help="Manage prompt templates.", invoke_without_command=True)


@template_app.callback()
def template_default(ctx: typer.Context) -> None:
    """Manage prompt templates."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(template_list, category="", json_output=False)


@template_app.command("save")
def template_save(
    text: str = typer.Argument(..., help="Prompt text to save as template"),
    name: str = typer.Option("", "--name", "-n", help="Template name (auto-generated if omitted)"),
    category: str = typer.Option(
        "", "--category", "-c", help="Category (auto-detected if omitted)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Save a prompt as a reusable template."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.templates import save_template
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    result = save_template(
        db,
        text=text,
        name=name or None,
        category=category or None,
    )
    if json_output:
        print(json_mod.dumps(result, indent=2, default=str))
    else:
        typer.echo(f"Saved template '{result['name']}' (category: {result['category']})")


@template_app.command("list")
def template_list(
    category: str = typer.Option("", "--category", "-c", help="Filter by category"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    smart: bool = typer.Option(False, "--smart", help="Sort by relevance score"),
) -> None:
    """List your saved prompt templates."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.output.terminal import render_templates
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    items = db.list_templates(category=category or None)

    if smart and items:
        # Sort by effectiveness_score descending if available, else keep original order
        items.sort(
            key=lambda t: t.get("effectiveness_score", 0) or 0,
            reverse=True,
        )

    if json_output:
        print(json_mod.dumps(items, indent=2, default=str))
    else:
        print(render_templates(items, category_filter=category or None), end="")


@template_app.command("use")
def template_use(
    name: str = typer.Argument(..., help="Template name to use"),
    variables: list[str] = typer.Argument(None, help="Variables as key=value pairs"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy rendered template to clipboard"),
) -> None:
    """Use a saved template with variable substitution."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.templates import extract_variables, render_template
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    template = db.get_template(name)

    if template is None:
        console.print(f"[red]Template '{name}' not found.[/red]")
        console.print("Run [bold]reprompt template list[/bold] to see available templates.")
        raise typer.Exit(1)

    text = template["text"]

    # Parse key=value pairs
    var_dict: dict[str, str] = {}
    for v in variables or []:
        if "=" in v:
            key, val = v.split("=", 1)
            var_dict[key] = val

    rendered = render_template(text, var_dict)

    if json_output:
        remaining = extract_variables(rendered)
        print(
            json_mod.dumps(
                {
                    "rendered": rendered,
                    "template_name": name,
                    "unfilled_variables": remaining,
                },
                indent=2,
            )
        )
    else:
        # Show unfilled variables as hint
        remaining = extract_variables(rendered)
        if remaining:
            console.print(f"[dim]Unfilled variables: {', '.join(remaining)}[/dim]")
        console.print(rendered)

    if copy:
        _copy_to_clip(rendered)

    db.increment_template_usage(name)


def _register_late_commands() -> None:
    """Register commands after all @app.command() definitions to control help panel order."""
    from reprompt.commands.telemetry import telemetry_app
    from reprompt.commands.wrapped import wrapped

    app.add_typer(template_app, name="template", rich_help_panel="Manage")
    app.command(rich_help_panel="Manage")(wrapped)
    app.add_typer(
        telemetry_app,
        name="telemetry",
        help="Manage anonymous telemetry",
        rich_help_panel="Setup",
    )


def _load_plugins() -> None:
    """Auto-discover and load reprompt plugins (e.g. reprompt-pro)."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="reprompt.plugins")
        for ep in eps:
            try:
                register_fn = ep.load()
                register_fn(app)
            except Exception as exc:
                logger.debug("Failed to load plugin %s: %s", ep.name, exc)
    except Exception:
        pass


_load_plugins()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"reprompt {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True
    ),
    json_output: bool = typer.Option(False, "--json", help="Output dashboard as JSON"),
) -> None:
    """reprompt -- Discover, analyze, and evolve your best prompts from AI coding sessions."""
    if ctx.invoked_subcommand is not None:
        return

    # Dashboard mode
    from reprompt.config import Settings
    from reprompt.core.dashboard import build_dashboard_data
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    data = build_dashboard_data(db)

    if json_output:
        import dataclasses
        import json as json_mod

        typer.echo(json_mod.dumps(dataclasses.asdict(data), indent=2, default=str))
    else:
        from reprompt.output.dashboard_terminal import render_dashboard

        typer.echo(render_dashboard(data), nl=False)


@app.command(rich_help_panel="Analyze")
def scan(
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Filter by source (e.g. claude-code, cursor, aider)",
    ),
    path: str | None = typer.Option(None, help="Custom session path"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Skip auto-report after scan"),
) -> None:
    """Scan AI tool sessions for prompts.

    Examples:

        reprompt scan                                    # scan all AI tools

        reprompt scan --source cursor                    # scan Cursor only

        reprompt scan --source chatgpt-export --path ~/Downloads/conversations.json
    """
    from reprompt.config import Settings
    from reprompt.core.pipeline import build_report_data, run_scan
    from reprompt.output.terminal import render_report
    from reprompt.storage.db import PromptDB

    settings = Settings()
    result = run_scan(source=source, path=path, settings=settings)

    console.print("[bold]Scan complete[/bold]")
    console.print(f"  Sessions scanned: {result.sessions_scanned}")
    console.print(f"  Prompts found:    {result.total_parsed}")
    console.print(f"  Unique:           {result.unique_after_dedup}")
    console.print(f"  Duplicates:       {result.duplicates}")
    console.print(f"  New stored:       {result.new_stored}")

    # Auto-show report after scan (skip with --quiet)
    if not quiet and result.unique_after_dedup > 0:
        data = build_report_data(settings=settings)
        print(render_report(data), end="")

    # Suggest install-hook if not already set up (show once)
    db = PromptDB(settings.db_path)
    stats = db.get_stats()
    if stats.get("total_prompts", 0) > 0:
        hook_installed = (Path.home() / ".claude" / "settings.json").exists() and _hook_registered()
        if not hook_installed and db.get_setting("hook_suggestion_shown") is None:
            console.print(
                "\n[dim]Tip: auto-run reprompt after each session "
                "\u2192  reprompt install-hook claude-code[/dim]"
            )
            db.set_setting("hook_suggestion_shown", "1")

    # Next steps for new users (show once, on first scan with data)
    if result.new_stored > 0 and stats.get("total_prompts", 0) <= result.new_stored + 10:
        console.print("\n[bold]Try next:[/bold]")
        console.print('  reprompt score [dim]"your prompt"[/dim]   — instant quality score')
        console.print("  reprompt template list         — see your prompt patterns")
        console.print("  reprompt insights             — personal analysis")
    else:
        if result.unique_after_dedup > 0:
            _show_hint(db, "scan")


def _hook_registered() -> bool:
    """Check if reprompt hook is registered in Claude Code settings."""
    import json

    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text())
        hooks = data.get("hooks", {}).get("Stop", [])
        return any(isinstance(h, dict) and "reprompt" in h.get("command", "") for h in hooks)
    except (json.JSONDecodeError, KeyError):
        return False


def _detect_import_source(path: Path) -> str | None:
    """Auto-detect the source format of an import file."""
    import json as _json

    try:
        suffix = path.suffix.lower()
        if suffix in (".zip", ".dms"):
            # Claude.ai exports come as ZIP/.dms
            return "claude-chat"
        raw = path.read_text(encoding="utf-8")
        data = _json.loads(raw)
    except (OSError, _json.JSONDecodeError, UnicodeDecodeError):
        return None

    # Normalize to list
    items = data if isinstance(data, list) else [data]
    if not items:
        return None

    first = items[0]
    if isinstance(first, dict):
        if "mapping" in first:
            return "chatgpt"
        if "chat_messages" in first:
            return "claude-chat"
    return None


@app.command(name="import", rich_help_panel="Analyze")
def import_file(
    file: str = typer.Argument(..., help="Path to export file (JSON or ZIP)"),
    source: str | None = typer.Option(
        None, help="Source format: chatgpt, claude-chat (auto-detected if omitted)"
    ),
) -> None:
    """Import prompts from a Chat AI export file."""
    from reprompt.adapters.chatgpt import ChatGPTAdapter
    from reprompt.adapters.claude_chat import ClaudeChatAdapter
    from reprompt.config import Settings
    from reprompt.core.dedup import DedupEngine
    from reprompt.core.extractors import extract_features
    from reprompt.core.scorer import score_prompt
    from reprompt.storage.db import PromptDB

    settings = Settings()
    path = Path(file)

    if not path.exists():
        console.print(f"[red]Error: file not found: {file}[/red]")
        raise typer.Exit(1)

    # Resolve source
    detected = source or _detect_import_source(path)
    if detected is None:
        console.print("[red]Error: could not detect source format. Use --source.[/red]")
        raise typer.Exit(1)

    adapter_map = {
        "chatgpt": ChatGPTAdapter,
        "claude-chat": ClaudeChatAdapter,
    }
    adapter_cls = adapter_map.get(detected)
    if adapter_cls is None:
        console.print(
            f"[red]Error: unknown source '{detected}'. Use: {', '.join(adapter_map)}[/red]"
        )
        raise typer.Exit(1)

    adapter = adapter_cls()
    prompts = adapter.parse_session(path)

    if not prompts:
        console.print("[yellow]No prompts found in file.[/yellow]")
        return

    # Dedup
    engine = DedupEngine(
        backend=settings.embedding_backend,
        threshold=settings.dedup_threshold,
        ollama_url=settings.ollama_url,
    )
    unique, dupes = engine.deduplicate(prompts)

    # Store
    db = PromptDB(settings.db_path)
    new_stored = 0
    for p in unique:
        if db.insert_prompt(
            p.text,
            source=p.source,
            project=p.project or "",
            session_id=p.session_id,
            timestamp=p.timestamp,
        ):
            new_stored += 1

    # Extract features for new prompts
    for p in unique:
        try:
            dna = extract_features(
                p.text, source=p.source, session_id=p.session_id, project=p.project
            )
            breakdown = score_prompt(dna)
            dna.overall_score = breakdown.total
            db.store_features(dna.prompt_hash, dna.to_dict())
        except Exception:
            import logging

            logging.getLogger("reprompt.cli").debug(
                "Feature extraction failed during import: %s", exc_info=True
            )

    # Mark file as processed
    db.mark_session_processed(str(path), source=adapter.name)

    console.print(f"[bold]Import complete[/bold] ({adapter.name})")
    console.print(f"  Prompts found:  {len(prompts)}")
    console.print(f"  Unique:         {len(unique)}")
    console.print(f"  Duplicates:     {len(dupes)}")
    console.print(f"  New stored:     {new_stored}")


@app.command(rich_help_panel="Analyze")
def report(
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    html: bool = typer.Option(False, "--html", help="Generate interactive HTML dashboard"),
    output: str = typer.Option("", "--output", "-o", help="Output file path (for --html)"),
    top: int = typer.Option(20, help="Number of top terms to show"),
    clusters: int = typer.Option(0, "--clusters", help="Number of clusters (0 = auto-select)"),
    source: str = typer.Option(
        "",
        "--source",
        "-s",
        help="Filter by source (e.g. chatgpt-export, claude-code)",
    ),
) -> None:
    """Generate analytics report."""
    from reprompt.config import Settings
    from reprompt.core.pipeline import build_report_data

    settings = Settings()
    n_clusters_arg = clusters if clusters > 0 else None
    source_filter = source if source else None
    data = build_report_data(settings=settings, n_clusters=n_clusters_arg, source=source_filter)

    # Early exit with guidance when DB is empty
    total = data.get("overview", {}).get("total_prompts", 0)
    if total == 0:
        console.print(
            "No prompts found. Run [bold]reprompt scan[/bold] to analyze your AI sessions."
        )
        return

    if html:
        import webbrowser
        from pathlib import Path

        from reprompt.core.digest import build_digest
        from reprompt.core.recommend import compute_recommendations
        from reprompt.core.trends import compute_trends
        from reprompt.output.html_report import render_html_dashboard
        from reprompt.storage.db import PromptDB

        db = PromptDB(settings.db_path)
        trends_data = compute_trends(db, period="7d", n_windows=6)
        recommend_data = compute_recommendations(db)
        try:
            digest_data = build_digest(db, period="7d")
        except Exception:
            digest_data = None

        html_content = render_html_dashboard(data, trends_data, recommend_data, digest_data)
        out_path = Path(output) if output else Path("reprompt-report.html")
        out_path.write_text(html_content, encoding="utf-8")

        typer.echo(f"Dashboard saved to {out_path.resolve()}")
        webbrowser.open(f"file://{out_path.resolve()}")
    elif format == "json":
        from reprompt.output.json_out import format_json_report

        print(format_json_report(data))
    else:
        from reprompt.output.terminal import render_report
        from reprompt.storage.db import PromptDB

        print(render_report(data), end="")
        _show_hint(PromptDB(settings.db_path), "report")


@app.command(deprecated=True, hidden=True)
def library(
    category: str | None = typer.Option(None, help="Filter by category"),
    export: str | None = typer.Argument(None, help="Export to file path (Markdown)"),
) -> None:
    """Deprecated: use `reprompt template list` instead."""
    console.print("[dim]library is now part of template list.[/dim]")
    console.print("[dim]Run: reprompt template list[/dim]")
    raise typer.Exit(0)


@app.command(rich_help_panel="Analyze")
def search(
    query: str = typer.Argument(..., help="Search term (case-insensitive)"),
    limit: int = typer.Option(20, help="Maximum results to show"),
    source: str = typer.Option(
        "",
        "--source",
        "-s",
        help="Filter by source (e.g. chatgpt-export, claude-code)",
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy results to clipboard"),
) -> None:
    """Search your prompt history by keyword."""
    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    source_filter = source if source else None
    results = db.search_prompts(query, source=source_filter, limit=limit)

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

    if copy:
        lines = [p.get("text", "") for p in results]
        _copy_to_clip("\n\n".join(lines))


@app.command(deprecated=True, hidden=True)
def trends(
    period: str = typer.Option("7d", help="Time bucket size: 7d, 14d, 30d, 1m"),
    windows: int = typer.Option(4, help="Number of periods to compare"),
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    source: str | None = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
) -> None:
    """Deprecated: use `reprompt digest --trends` instead."""
    console.print("[dim]trends is now part of digest --trends.[/dim]")
    console.print("[dim]Run: reprompt digest --trends[/dim]")
    raise typer.Exit(0)


@app.command(deprecated=True, hidden=True)
def effectiveness(
    top: int = typer.Option(10, help="Show top N patterns by effectiveness"),
    worst: int = typer.Option(3, help="Show bottom N patterns"),
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
) -> None:
    """Deprecated: use `reprompt insights` instead."""
    typer.echo(
        "Warning: 'effectiveness' is deprecated. Use 'reprompt insights' instead.",
        err=True,
    )
    insights(json_output=(format == "json"), source=None)


@app.command(rich_help_panel="Manage")
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


@app.command("mcp-serve", rich_help_panel="Setup")
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


@app.command(rich_help_panel="Manage")
def purge(
    older_than: str = typer.Option("90d", help="Delete prompts older than (e.g. 90d)"),
    all_: bool = typer.Option(
        False,
        "--all",
        help="Delete ALL data and reset the database (clears demo data, all sessions, etc.)",
    ),
) -> None:
    """Clean up old data."""
    import re

    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    if all_:
        stats = db.get_stats()
        total = stats.get("total_prompts", 0)
        if total > 0:
            confirm = typer.confirm(
                f"This will delete all {total} prompts and reset the database. Continue?"
            )
            if not confirm:
                raise typer.Abort()
        deleted = db.purge_all()
        console.print(f"[bold red]Purged all {deleted} prompts and reset database[/bold red]")
        console.print("Run [bold]reprompt scan[/bold] to re-import your sessions.")
        return

    m = re.fullmatch(r"(\d+)d?", older_than.strip(), re.IGNORECASE)
    if not m:
        raise typer.BadParameter("Use format like '90d' or '30'")
    days = int(m.group(1))
    deleted = db.purge_old_prompts(days)
    console.print(f"Purged {deleted} prompts older than {days} days")


@app.command(deprecated=True, hidden=True)
def recommend(
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
) -> None:
    """Deprecated: use `reprompt template list --smart` instead."""
    console.print("[dim]recommend is now part of template list --smart.[/dim]")
    console.print("[dim]Run: reprompt template list --smart[/dim]")
    raise typer.Exit(0)


@app.command("merge-view", deprecated=True, hidden=True)
def merge_view(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    limit: int = typer.Option(0, "--limit", help="Max clusters to show (0 = all)"),
) -> None:
    """Deprecated: use `reprompt insights` instead."""
    typer.echo(
        "Warning: 'merge-view' is deprecated. Use 'reprompt insights' instead.",
        err=True,
    )
    insights(json_output=json_output, source=None)


@app.command(deprecated=True, hidden=True)
def save(
    text: str = typer.Argument(..., help="Prompt text to save as template"),
    name: str = typer.Option("", "--name", "-n", help="Template name (auto-generated if omitted)"),
    category: str = typer.Option(
        "", "--category", "-c", help="Category (auto-detected if omitted)"
    ),
) -> None:
    """Deprecated: use `reprompt template save` instead."""
    template_save(text=text, name=name, category=category, json_output=False)


@app.command(deprecated=True, hidden=True)
def templates(
    category: str = typer.Option("", "--category", "-c", help="Filter by category"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Deprecated: use `reprompt template list` instead."""
    template_list(category=category, json_output=json_output)


@app.command(rich_help_panel="Analyze")
def style(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    source: str | None = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
    trends: bool = typer.Option(False, "--trends", help="Show style change trends"),
    period: str = typer.Option("7d", "--period", help="Comparison period (with --trends)"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Show your personal prompting style fingerprint."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    if trends:
        from reprompt.core.style import compute_style_trends
        from reprompt.output.terminal import render_style_trends

        data = compute_style_trends(db, period=period, source=source)

        if json_output:
            print(json_mod.dumps(data, indent=2))
        else:
            print(render_style_trends(data), end="")
        if copy:
            _copy_to_clip(json_mod.dumps(data, indent=2), quiet=json_output)
        return

    from reprompt.core.library import categorize_prompt
    from reprompt.core.style import compute_style
    from reprompt.output.terminal import render_style

    rows = db.get_all_prompts(source=source)
    prompts = [
        {
            "text": r["text"],
            "category": categorize_prompt(r["text"]),
            "char_count": r.get("char_count", len(r["text"])),
        }
        for r in rows
        if r.get("duplicate_of") is None
    ]

    data = compute_style(prompts)

    if json_output:
        print(json_mod.dumps(data, indent=2))
    else:
        print(render_style(data), end="")

    if copy:
        _copy_to_clip(json_mod.dumps(data, indent=2), quiet=json_output)


@app.command(deprecated=True, hidden=True)
def use(
    name: str = typer.Argument(..., help="Template name to use"),
    variables: list[str] = typer.Argument(None, help="Variables as key=value pairs"),
) -> None:
    """Deprecated: use `reprompt template use` instead."""
    template_use(name=name, variables=variables, json_output=False, copy=False)


@app.command(rich_help_panel="Optimize")
def lint(
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
    path: str = typer.Option(None, help="Path to scan for session files"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    fail_on_warning: bool = typer.Option(False, "--strict", help="Exit 1 on warnings too"),
    score_threshold: int = typer.Option(
        0, "--score-threshold", help="Fail if avg prompt score < threshold (CI mode)"
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="Target model for model-specific rules (claude/gpt/gemini)"
    ),
    max_tokens: int = typer.Option(
        0, "--max-tokens", help="Warn when prompts exceed token budget (0 = disabled)"
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Check prompt quality against lint rules.

    Scans session history and checks each prompt for quality issues:
    - min-length: prompts under 20 chars
    - short-prompt: prompts under 40 chars (warning)
    - vague-prompt: overly vague prompts like "fix it"
    - debug-needs-reference: debug prompts without file/function references
    - max-tokens: prompt exceeds token budget

    Model-specific rules (--model):
    - claude: suggests XML tags for structure
    - gpt: warns on XML tags (may echo verbatim), prefers markdown
    - gemini: warns on very long prompts

    CI mode: use --score-threshold to fail if average score is below a threshold.

    Examples:

        reprompt lint                                    # lint stored prompts

        reprompt lint --model claude                     # with Claude-specific hints

        reprompt lint --score-threshold 50               # fail if avg score < 50 (CI mode)

        reprompt lint --strict --json                    # strict mode with JSON output
    """
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.lint import format_lint_results, lint_prompts, load_lint_config
    from reprompt.core.pipeline import get_adapters
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    # Load lint config from .reprompt.toml / pyproject.toml
    lint_config = load_lint_config()

    # CLI flags override config file
    effective_threshold = score_threshold if score_threshold > 0 else lint_config.score_threshold
    if model:
        lint_config.model = model.lower()
    if max_tokens > 0:
        lint_config.max_tokens = max_tokens

    # Collect prompts from DB (already scanned)
    rows = db.get_all_prompts()
    texts = [r["text"] for r in rows]

    if not texts:
        # If DB is empty, try scanning directly
        adapters = get_adapters()
        if source:
            adapters = [a for a in adapters if a.name == source]

        from pathlib import Path as P

        for adapter in adapters:
            if path:
                scan_root = P(path)
            else:
                scan_root = P(adapter.default_session_path).expanduser()
            if not scan_root.exists():
                continue
            if hasattr(adapter, "discover_sessions"):
                for sf in adapter.discover_sessions():
                    texts.extend(p.text for p in adapter.parse_session(sf))
            else:
                ext = "*.vscdb" if adapter.name == "cursor" else "*.jsonl"
                for sf in sorted(scan_root.rglob(ext)):
                    texts.extend(p.text for p in adapter.parse_session(sf))

    if not texts:
        console.print("No prompts found. Run [bold]reprompt scan[/bold] first.")
        raise typer.Exit(0)

    violations = lint_prompts(texts, config=lint_config)

    # Score threshold mode (CI integration)
    score_data = None
    if effective_threshold > 0:
        from reprompt.core.extractors import extract_features
        from reprompt.core.scorer import score_prompt

        scores = []
        for t in texts:
            dna = extract_features(t, source="lint", session_id="lint-ci")
            scores.append(score_prompt(dna).total)
        avg_score = sum(scores) / len(scores) if scores else 0
        score_data = {
            "avg_score": round(avg_score, 1),
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "threshold": effective_threshold,
            "pass": avg_score >= effective_threshold,
        }

    if json_output:
        data = {
            "total_prompts": len(texts),
            "violations": [
                {
                    "rule": v.rule,
                    "severity": v.severity,
                    "message": v.message,
                    "prompt": v.prompt_text[:100],
                }
                for v in violations
            ],
            "errors": sum(1 for v in violations if v.severity == "error"),
            "warnings": sum(1 for v in violations if v.severity == "warning"),
        }
        if score_data:
            data["score"] = score_data
        print(json_mod.dumps(data, indent=2))
    else:
        lint_output = format_lint_results(violations, len(texts))
        print(lint_output)
        if score_data:
            status = "[green]PASS[/green]" if score_data["pass"] else "[red]FAIL[/red]"
            console.print(
                f"\n  Score: avg {score_data['avg_score']}/100"
                f" (min {score_data['min_score']}, max {score_data['max_score']})"
                f" — threshold {effective_threshold} → {status}"
            )

    if copy:
        if json_output:
            _copy_to_clip(json_mod.dumps(data, indent=2), quiet=True)
        else:
            _copy_to_clip(lint_output)

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    if errors or (fail_on_warning and warnings):
        raise typer.Exit(1)
    if score_data and not score_data["pass"]:
        raise typer.Exit(1)


@app.command(rich_help_panel="Analyze")
def check(
    text: str = typer.Argument(..., help="Prompt text to check (use '-' for stdin)"),
    model: str = typer.Option("", "--model", "-m", help="Target model (claude/gpt/gemini)"),
    max_tokens: int = typer.Option(0, "--max-tokens", help="Token budget (0 = disabled)"),
    file: str = typer.Option("", "--file", "-f", help="Read prompt from file"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy rewritten prompt to clipboard"),
) -> None:
    """Full prompt diagnostic — score + lint + rewrite in one command.

    Runs all quality checks and shows a unified report with score breakdown,
    strengths, suggestions, lint issues, and auto-rewrite preview.

    Examples:

        reprompt check "fix the auth bug in login.ts"

        reprompt check "refactor the middleware" --model claude

        reprompt check "help me debug this crash" --json
    """
    text = _resolve_text(text, file)
    from reprompt.core.check import check_prompt

    result = check_prompt(text, model=model, max_tokens=max_tokens)

    if json_output:
        import json as json_mod

        data = {
            "total": result.total,
            "tier": result.tier,
            "clarity": result.clarity,
            "context": result.context,
            "position": result.position,
            "structure": result.structure,
            "repetition": result.repetition,
            "word_count": result.word_count,
            "token_count": result.token_count,
            "confirmations": result.confirmations,
            "suggestions": result.suggestions,
            "lint_issues": result.lint_issues,
            "rewritten": result.rewritten,
            "rewrite_delta": result.rewrite_delta,
            "rewrite_changes": result.rewrite_changes,
        }
        typer.echo(json_mod.dumps(data, indent=2, ensure_ascii=False))
    else:
        from reprompt.output.check_terminal import render_check

        typer.echo(render_check(result))

    if copy:
        _copy_to_clip(result.rewritten, quiet=json_output)

    if not json_output:
        from reprompt.config import Settings as _S
        from reprompt.storage.db import PromptDB as _DB

        _show_hint(_DB(_S().db_path), "check", json_output=json_output)


@app.command(rich_help_panel="Analyze")
def explain(
    text: str = typer.Argument(..., help="Prompt text to explain (use '-' for stdin)"),
    file: str = typer.Option("", "--file", "-f", help="Read prompt from file"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Explain what makes a prompt good or bad in plain English.

    Analyzes the prompt and provides educational feedback: what's working,
    what's missing, and specific tips to improve. No LLM needed.

    Examples:

        reprompt explain "fix the auth bug"

        reprompt explain --file prompt.txt --json
    """
    text = _resolve_text(text, file)
    from reprompt.core.explain import explain_prompt

    result = explain_prompt(text)

    if json_output:
        import json as json_mod

        data = {
            "score": result.score,
            "tier": result.tier,
            "summary": result.summary,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "tips": result.tips,
        }
        typer.echo(json_mod.dumps(data, indent=2, ensure_ascii=False))
    else:
        from reprompt.output.explain_terminal import render_explain

        typer.echo(render_explain(result))

    if not json_output:
        from reprompt.config import Settings as _S
        from reprompt.storage.db import PromptDB as _DB

        _show_hint(_DB(_S().db_path), "explain", json_output=json_output)


@app.command(rich_help_panel="Analyze")
def score(
    text: str = typer.Argument(..., help="Prompt text to score (use '-' for stdin)"),
    file: str = typer.Option("", "--file", "-f", help="Read prompt from file"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Score a prompt using research-backed analysis.

    Examples:

        reprompt score "Fix the auth bug in login.ts where JWT expires"

        reprompt score --file prompt.txt --json

        reprompt score "Fix bug" --copy
    """
    text = _resolve_text(text, file)
    from reprompt.core.cost import estimate_cost, format_cost, model_for_source
    from reprompt.core.extractors import extract_features
    from reprompt.core.scorer import score_prompt

    dna = extract_features(text, source="manual", session_id="score-cli")
    breakdown = score_prompt(dna)
    dna.overall_score = breakdown.total

    cost_usd = estimate_cost(dna.token_count, source="manual")
    cost_info = {
        "tokens": dna.token_count,
        "model": model_for_source("manual"),
        "cost_usd": round(cost_usd, 6),
        "cost_display": format_cost(cost_usd),
    }

    if json_output:
        import json as json_mod

        data = {
            "total": breakdown.total,
            "structure": breakdown.structure,
            "context": breakdown.context,
            "position": breakdown.position,
            "repetition": breakdown.repetition,
            "clarity": breakdown.clarity,
            "task_type": dna.task_type,
            "word_count": dna.word_count,
            "token_count": dna.token_count,
            "estimated_cost": cost_info,
            "context_specificity": dna.context_specificity,
            "ambiguity_score": dna.ambiguity_score,
            "suggestions": [
                {
                    "category": s.category,
                    "paper": s.paper,
                    "message": s.message,
                    "impact": s.impact,
                    "points": s.points,
                }
                for s in breakdown.suggestions
            ],
            "confirmations": [
                {
                    "category": c.category,
                    "message": c.message,
                    "score": c.score,
                }
                for c in breakdown.confirmations
            ],
        }
        typer.echo(json_mod.dumps(data, indent=2))
    else:
        from reprompt.output.terminal import render_score

        data = {
            "total": breakdown.total,
            "structure": breakdown.structure,
            "context": breakdown.context,
            "position": breakdown.position,
            "repetition": breakdown.repetition,
            "clarity": breakdown.clarity,
            "estimated_cost": cost_info,
            "suggestions": [
                {
                    "category": s.category,
                    "paper": s.paper,
                    "message": s.message,
                    "impact": s.impact,
                    "points": s.points,
                }
                for s in breakdown.suggestions
            ],
            "confirmations": [
                {
                    "category": c.category,
                    "message": c.message,
                    "score": c.score,
                }
                for c in breakdown.confirmations
            ],
        }
        typer.echo(render_score(data))
        from reprompt.config import Settings as _S
        from reprompt.storage.db import PromptDB as _DB

        _show_hint(_DB(_S().db_path), "score")

    if copy:
        import json as json_mod

        copy_data = {
            "total": breakdown.total,
            "structure": breakdown.structure,
            "context": breakdown.context,
            "position": breakdown.position,
            "repetition": breakdown.repetition,
            "clarity": breakdown.clarity,
            "task_type": dna.task_type,
            "word_count": dna.word_count,
        }
        _copy_to_clip(json_mod.dumps(copy_data, indent=2), quiet=json_output)


@app.command(rich_help_panel="Optimize")
def compress(
    text: str = typer.Argument(..., help="Prompt text to compress (use '-' for stdin)"),
    file: str = typer.Option("", "--file", "-f", help="Read prompt from file"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy compressed text to clipboard"),
) -> None:
    """Compress a prompt by removing filler words and simplifying phrases.

    Examples:

        reprompt compress "Can you please help me refactor this code?"

        reprompt compress --file prompt.txt --json

        reprompt compress "verbose prompt here" --copy
    """
    text = _resolve_text(text, file)
    from reprompt.core.compress import compress_text

    result = compress_text(text)

    if json_output:
        import json as json_mod
        from dataclasses import asdict

        typer.echo(json_mod.dumps(asdict(result), indent=2, ensure_ascii=False))
    else:
        from reprompt.output.compress_terminal import render_compress

        typer.echo(render_compress(result))

    if copy:
        _copy_to_clip(result.compressed, quiet=json_output)


@app.command(rich_help_panel="Optimize")
def rewrite(
    text: str = typer.Argument(..., help="Prompt text to improve (use '-' for stdin)"),
    file: str = typer.Option("", "--file", "-f", help="Read prompt from file"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    diff: bool = typer.Option(False, "--diff", help="Show unified diff (red/green)"),
    copy: bool = typer.Option(False, "--copy", help="Copy rewritten text to clipboard"),
) -> None:
    """Rewrite a prompt to improve its score. Rule-based, no LLM needed.

    Applies 4 layers: filler removal, instruction front-loading,
    key requirement echo, and hedging cleanup. Also suggests manual
    improvements you can make.

    Examples:

        reprompt rewrite "I was wondering if you could fix the authentication bug"

        reprompt rewrite --file prompt.txt --diff

        reprompt rewrite "please help me refactor this code to be better" --copy
    """
    text = _resolve_text(text, file)
    from reprompt.core.rewrite import rewrite_prompt

    result = rewrite_prompt(text)

    if json_output:
        import json as json_mod

        data = {
            "original": result.original,
            "rewritten": result.rewritten,
            "score_before": result.score_before,
            "score_after": result.score_after,
            "score_delta": result.score_delta,
            "changes": result.changes,
            "manual_suggestions": result.manual_suggestions,
        }
        typer.echo(json_mod.dumps(data, indent=2, ensure_ascii=False))
    elif diff:
        from reprompt.output.rewrite_terminal import render_rewrite_diff

        typer.echo(render_rewrite_diff(result))
    else:
        from reprompt.output.rewrite_terminal import render_rewrite

        typer.echo(render_rewrite(result))

    if copy:
        _copy_to_clip(result.rewritten, quiet=json_output)

    if not json_output:
        from reprompt.config import Settings as _S
        from reprompt.storage.db import PromptDB as _DB

        _show_hint(_DB(_S().db_path), "rewrite", json_output=json_output)


@app.command(rich_help_panel="Optimize")
def build(
    task: str = typer.Argument(..., help="What the AI should do"),
    context: str = typer.Option("", "--context", "-c", help="Background information"),
    file: list[str] = typer.Option([], "--file", "-f", help="File references (repeatable)"),
    error: str = typer.Option("", "--error", "-e", help="Error message or stack trace"),
    constraint: list[str] = typer.Option([], "--constraint", help="Constraints (repeatable)"),
    example: str = typer.Option("", "--example", help="Example input/output"),
    output_format: str = typer.Option("", "--output-format", help="Expected response format"),
    role: str = typer.Option("", "--role", "-r", help="AI role/persona"),
    model: str = typer.Option("", "--model", "-m", help="Target model (claude/gpt/gemini)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy built prompt to clipboard"),
) -> None:
    """Build a well-structured prompt from components.

    Assembles a prompt that maximizes quality score by combining
    your task with context, files, errors, and constraints.

    Examples:

        reprompt build "fix the auth bug"

        reprompt build "fix the crash" --file src/auth.ts --error "TypeError: ..."

        reprompt build "refactor" -f src/app.py --constraint "keep tests" --model claude
    """
    from reprompt.core.build import build_prompt

    result = build_prompt(
        task,
        context=context,
        files=file if file else None,
        error=error,
        constraints=constraint if constraint else None,
        examples=example,
        output_format=output_format,
        role=role,
        model=model,
    )

    if json_output:
        import json as json_mod

        data = {
            "prompt": result.prompt,
            "score": result.score,
            "tier": result.tier,
            "components_used": result.components_used,
            "suggestions": result.suggestions,
        }
        typer.echo(json_mod.dumps(data, indent=2, ensure_ascii=False))
    else:
        from reprompt.output.build_terminal import render_build

        typer.echo(render_build(result))

    if copy:
        _copy_to_clip(result.prompt, quiet=json_output)

    if not json_output:
        from reprompt.config import Settings as _S
        from reprompt.storage.db import PromptDB as _DB

        _show_hint(_DB(_S().db_path), "build", json_output=json_output)


@app.command(rich_help_panel="Optimize")
def distill(
    session_id: str = typer.Argument(None, help="Session ID to distill"),
    last: int = typer.Option(1, "--last", help="Distill the N most recent sessions"),
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
    summary: bool = typer.Option(False, "--summary", help="Show compressed summary"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
    threshold: float = typer.Option(0.3, "--threshold", help="Importance cutoff (0.0-1.0)"),
    export: bool = typer.Option(False, "--export", help="Output as context recovery document"),
    full: bool = typer.Option(False, "--full", help="Include assistant responses (with --export)"),
    show_weights: bool = typer.Option(
        False, "--show-weights", help="Print signal weights and exit"
    ),
    weights: str = typer.Option(
        None, "--weights", help="Override weights, e.g. 'semantic_shift=0.4'"
    ),
) -> None:
    """Distill a conversation to its most important turns.

    Examples:

        reprompt distill                                 # distill most recent session

        reprompt distill --last 3 --summary              # summarize last 3 sessions

        reprompt distill --export --full                 # export context for a new session
    """
    # --show-weights: print and exit
    if show_weights:
        from reprompt.core.distill import DEFAULT_WEIGHTS

        for k, v in DEFAULT_WEIGHTS.items():
            typer.echo(f"  {k}={v}")
        return

    # --full without --export: warn
    if full and not export:
        typer.echo("--full has no effect without --export", err=True)

    # --export with --last > 1: error
    if export and not session_id and last > 1:
        typer.echo("--export works with a single session. Use --last 1 or specify a session ID.")
        raise typer.Exit(code=1)

    # --export and --summary are mutually exclusive
    if export and summary:
        typer.echo("--export and --summary are mutually exclusive.")
        raise typer.Exit(code=1)

    # Parse --weights override
    weights_dict: dict[str, float] | None = None
    if weights:
        from reprompt.core.distill import DEFAULT_WEIGHTS

        weights_dict = {}
        for pair in weights.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, val = pair.split("=", 1)
            key = key.strip()
            if key not in DEFAULT_WEIGHTS:
                typer.echo(
                    f"Unknown weight key: '{key}'. Valid keys: {', '.join(DEFAULT_WEIGHTS.keys())}"
                )
                raise typer.Exit(code=1)
            weights_dict[key] = float(val)
        total = sum({**DEFAULT_WEIGHTS, **weights_dict}.values())
        if abs(total - 1.0) > 0.05:
            typer.echo(f"Warning: weights sum to {total:.2f}, not 1.0", err=True)

    from reprompt.config import Settings
    from reprompt.core.distill import distill_conversation, generate_summary
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    # Resolve sessions
    sessions = _resolve_distill_sessions(db, session_id, last, source)

    if not sessions:
        if json_output:
            typer.echo("[]")
        else:
            typer.echo("No sessions found. Run `reprompt scan` first to import sessions.")
        return

    results = []
    target = last if not session_id else 1
    for file_path, adapter_source, resolved_sid in sessions:
        conv = _load_conversation(file_path, adapter_source, db, resolved_sid)
        if conv is None:
            continue
        result = distill_conversation(conv, threshold=threshold, weights=weights_dict)
        if summary:
            result.summary = generate_summary(result)
        results.append(result)
        if len(results) >= target:
            break

    if not results:
        if json_output:
            typer.echo("[]")
        else:
            typer.echo("Could not load any sessions.")
        return

    # Export mode
    if export:
        from reprompt.output.export import generate_export

        export_text = generate_export(results[0], full=full)
        if json_output:
            import json as json_mod

            envelope = {
                "export": export_text,
                "session_id": results[0].conversation.session_id,
                "source": results[0].conversation.source,
                "tokens": len(export_text) // 4,
            }
            typer.echo(json_mod.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            typer.echo(export_text)

        if copy:
            _copy_to_clip(export_text, quiet=json_output)
        return

    # Output
    if json_output:
        import json as json_mod
        from dataclasses import asdict

        output_data = [asdict(r) for r in results] if len(results) > 1 else asdict(results[0])
        typer.echo(json_mod.dumps(output_data, indent=2, ensure_ascii=False, default=str))
    else:
        from reprompt.output.distill_terminal import render_distill, render_distill_summary

        parts = []
        for result in results:
            if summary:
                parts.append(render_distill_summary(result))
            else:
                parts.append(render_distill(result))
        typer.echo("\n---\n".join(parts) if len(parts) > 1 else parts[0])
        _show_hint(db, "distill")

    if copy:
        if summary:
            copy_text = "\n---\n".join(r.summary or "" for r in results)
        else:
            copy_parts = []
            for result in results:
                for turn in result.filtered_turns:
                    prefix = "User" if turn.role == "user" else "Assistant"
                    copy_parts.append(f"[{prefix}] {turn.text}")
            copy_text = "\n\n".join(copy_parts)
        _copy_to_clip(copy_text, quiet=json_output)


def _resolve_distill_sessions(
    db: PromptDB, session_id: str | None, last: int, source: str | None
) -> list[tuple[str, str, str | None]]:
    """Resolve session file paths and sources for distill.

    Returns list of (file_path, adapter_source, resolved_session_id) tuples.
    """
    conn = db._conn()
    try:
        if session_id:
            row = conn.execute(
                "SELECT DISTINCT source FROM prompts WHERE session_id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
            if not row:
                return []
            found_source = row["source"]
            file_row = conn.execute(
                "SELECT file_path FROM processed_sessions WHERE file_path LIKE ? AND source = ?",
                (f"%{session_id}%", found_source),
            ).fetchone()
            if file_row:
                return [(file_row["file_path"], found_source, session_id)]
            return [("", found_source, session_id)]
        else:
            query = "SELECT file_path, source FROM processed_sessions"
            params: list[str] = []
            if source:
                query += " WHERE source = ?"
                params.append(source)
            query += " ORDER BY processed_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [(r["file_path"], r["source"], None) for r in rows]
    finally:
        conn.close()


def _load_conversation(
    file_path: str,
    adapter_source: str,
    db: PromptDB,
    resolved_session_id: str | None = None,
) -> Conversation | None:
    """Load a conversation from a session file via the appropriate adapter."""
    from datetime import datetime
    from pathlib import Path as PathLib

    from reprompt.core.conversation import Conversation, ConversationTurn
    from reprompt.core.pipeline import get_adapters

    path = PathLib(file_path) if file_path else PathLib("")

    adapters = get_adapters()
    adapter = None
    for a in adapters:
        if a.name == adapter_source:
            adapter = a
            break

    if adapter is None:
        return None

    if not file_path or not path.exists():
        # Fallback: DB-only mode
        lookup_id = resolved_session_id or path.stem
        conn = db._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM prompts WHERE session_id = ? ORDER BY id",
                (lookup_id,),
            ).fetchall()
            session_prompts = [dict(r) for r in rows]
        finally:
            conn.close()

        if not session_prompts:
            return None

        turns = [
            ConversationTurn(
                role="user",
                text=r["text"],
                timestamp=r.get("timestamp", ""),
                turn_index=i,
            )
            for i, r in enumerate(session_prompts)
        ]
        return Conversation(
            session_id=lookup_id,
            source=adapter_source,
            project=session_prompts[0].get("project"),
            turns=turns,
        )

    # Normal: parse from file
    turns = adapter.parse_conversation(path)
    if not turns:
        return None

    # Compute duration from timestamps
    duration = None
    start_time = None
    end_time = None
    timestamps = [t.timestamp for t in turns if t.timestamp]
    if len(timestamps) >= 2:
        start_time = timestamps[0]
        end_time = timestamps[-1]
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            duration = int((end_dt - start_dt).total_seconds())
        except (ValueError, TypeError):
            pass

    project = None
    if hasattr(adapter, "_project_from_path"):
        project = adapter._project_from_path(file_path)

    return Conversation(
        session_id=path.stem,
        source=adapter_source,
        project=project,
        turns=turns,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration,
    )


@app.command(rich_help_panel="Analyze")
def compare(
    prompt_a: str | None = typer.Argument(None, help="First prompt"),
    prompt_b: str | None = typer.Argument(None, help="Second prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    best_worst: bool = typer.Option(
        False, "--best-worst", help="Auto-select best and worst from DB"
    ),
    source: str | None = typer.Option(
        None, "--source", "-s", help="Filter by source (with --best-worst)"
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Compare two prompts side by side using Prompt DNA analysis.

    Examples:

        reprompt compare "fix bug" "Fix the login timeout in auth.py by adding retry logic"

        reprompt compare --best-worst                    # compare your best vs worst prompts

        reprompt compare --best-worst --source cursor
    """
    from typing import Any

    from reprompt.core.extractors import extract_features
    from reprompt.core.prompt_dna import PromptDNA
    from reprompt.core.scorer import ScoreBreakdown, score_prompt

    # Mutual exclusion guard
    if best_worst and (prompt_a or prompt_b):
        console.print("[red]--best-worst cannot be combined with prompt arguments[/red]")
        raise typer.Exit(1)
    if not best_worst and not (prompt_a and prompt_b):
        console.print("[red]Provide two prompts or use --best-worst[/red]")
        raise typer.Exit(1)

    prompt_a_text: str | None = None
    prompt_b_text: str | None = None

    if best_worst:
        from reprompt.config import Settings
        from reprompt.storage.db import PromptDB

        settings = Settings()
        db = PromptDB(settings.db_path)
        pair = db.get_best_worst_prompts(source=source)
        if pair is None:
            console.print(
                "Not enough scored prompts. Run [bold]reprompt scan[/bold]"
                " to build your score history."
            )
            raise typer.Exit(1)
        prompt_a = pair[0]  # best
        prompt_b = pair[1]  # worst
        prompt_a_text = prompt_a
        prompt_b_text = prompt_b

    # Type narrowing for mypy strict (guards above guarantee non-None)
    assert prompt_a is not None and prompt_b is not None

    dna_a = extract_features(prompt_a, source="manual", session_id="compare-a")
    dna_b = extract_features(prompt_b, source="manual", session_id="compare-b")
    score_a = score_prompt(dna_a)
    score_b = score_prompt(dna_b)

    def _build_data(dna: PromptDNA, sc: ScoreBreakdown) -> dict[str, object]:
        return {
            "total": sc.total,
            "structure": sc.structure,
            "context": sc.context,
            "position": sc.position,
            "repetition": sc.repetition,
            "clarity": sc.clarity,
            "word_count": dna.word_count,
            "task_type": dna.task_type,
            "context_specificity": dna.context_specificity,
            "ambiguity_score": dna.ambiguity_score,
        }

    result: dict[str, Any] = {
        "prompt_a": _build_data(dna_a, score_a),
        "prompt_b": _build_data(dna_b, score_b),
    }

    # Include prompt texts for --best-worst display
    if prompt_a_text:
        result["prompt_a_text"] = prompt_a_text
        result["prompt_b_text"] = prompt_b_text

    if json_output:
        import json as json_mod

        typer.echo(json_mod.dumps(result, indent=2))
    else:
        from reprompt.output.terminal import render_compare

        typer.echo(render_compare(result))

    if copy:
        import json as json_mod

        _copy_to_clip(json_mod.dumps(result, indent=2), quiet=json_output)


@app.command(rich_help_panel="Analyze")
def insights(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    source: str | None = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Show research-backed insights about your prompting patterns."""
    from reprompt.config import Settings
    from reprompt.core.insights import (
        compute_insights,
        get_cross_session_repetition_insight,
        get_effectiveness_insight,
        get_similar_prompts_insight,
    )
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    all_features = db.get_all_features(source=source)
    result = compute_insights(all_features)

    # Expanded sections
    eff_data = get_effectiveness_insight(db, source=source)
    sim_data = get_similar_prompts_insight(db, source=source)
    rep_data = get_cross_session_repetition_insight(db, source=source)

    if json_output:
        import json as json_mod

        result["effectiveness"] = eff_data
        result["similar_prompts"] = sim_data
        result["cross_session_repetition"] = rep_data
        typer.echo(json_mod.dumps(result, indent=2))
    else:
        from reprompt.output.terminal import (
            render_effectiveness_section,
            render_insights,
            render_similar_prompts_section,
        )

        typer.echo(render_insights(result))

        if eff_data:
            typer.echo(render_effectiveness_section(eff_data))
            console.print(
                '  [dim]\u2192 Try: reprompt score "prompt" (improve weak patterns)[/dim]'
            )

        if sim_data:
            typer.echo(render_similar_prompts_section(sim_data))
            console.print(
                '  [dim]\u2192 Try: reprompt template save "..." (reuse instead of rewrite)[/dim]'
            )

        if rep_data:
            rate_pct = f"{rep_data['repetition_rate'] * 100:.0f}%"
            n = rep_data["total_recurring_topics"]
            console.print("\n  [bold]Cross-Session Repetition[/bold]")
            console.print(f"  {rate_pct} of prompts recur across sessions ({n} topics)")
            for t in rep_data["top_topics"]:
                console.print(f'    "{t["canonical_text"]}" \u2014 {t["session_count"]} sessions')
            console.print("  [dim]\u2192 Try: reprompt repetition (full analysis)[/dim]")

        _show_hint(db, "insights")

    if copy:
        import json as json_mod

        result["effectiveness"] = eff_data
        result["similar_prompts"] = sim_data
        result["cross_session_repetition"] = rep_data
        _copy_to_clip(json_mod.dumps(result, indent=2), quiet=json_output)


@app.command(rich_help_panel="Manage")
def privacy(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
    deep: bool = typer.Option(
        False, "--deep", help="Scan prompts for sensitive content (API keys, passwords, PII)"
    ),
) -> None:
    """Show where your prompts went and how they may be used.

    Examples:

        reprompt privacy                                 # show what you sent where

        reprompt privacy --deep                          # scan for API keys, tokens, PII

        reprompt privacy --deep --json
    """
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    all_prompts = db.get_all_prompts()

    if deep:
        from reprompt.core.privacy_scan import scan_prompts

        scan_result = scan_prompts(all_prompts)

        if json_output:
            data = {
                "prompts_scanned": scan_result.prompts_scanned,
                "total_findings": len(scan_result.matches),
                "categories": {
                    cat: {
                        "count": count,
                        "sources": sorted(scan_result.category_sources.get(cat, set())),
                    }
                    for cat, count in scan_result.category_counts.items()
                },
                "matches": [
                    {
                        "category": m.category,
                        "pattern": m.pattern_name,
                        "redacted": m.matched_text,
                        "source": m.source,
                    }
                    for m in scan_result.matches
                ],
            }
            typer.echo(json_mod.dumps(data, indent=2))
        else:
            from reprompt.output.terminal import render_privacy_deep

            typer.echo(render_privacy_deep(scan_result))

        if copy:
            data = {
                "prompts_scanned": scan_result.prompts_scanned,
                "categories": dict(scan_result.category_counts),
            }
            _copy_to_clip(json_mod.dumps(data, indent=2), quiet=json_output)
        return

    from reprompt.core.privacy import compute_privacy_summary
    from reprompt.output.terminal import render_privacy

    source_counts: dict[str, int] = {}
    for p in all_prompts:
        src = p.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    summary = compute_privacy_summary(source_counts)

    # render_privacy expects "name" key per source; compute_privacy_summary uses "source"
    for src in summary.get("sources", []):
        src["name"] = src.pop("source", "unknown")

    if json_output:
        typer.echo(json_mod.dumps(summary, indent=2))
    else:
        typer.echo(render_privacy(summary))

    if copy:
        _copy_to_clip(json_mod.dumps(summary, indent=2), quiet=json_output)


@app.command(rich_help_panel="Analyze")
def digest(
    period: str = typer.Option("7d", help="Comparison window: 7d, 14d, 30d"),
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    quiet: bool = typer.Option(False, "--quiet", help="One-line summary (for hooks/cron)"),
    history: bool = typer.Option(False, "--history", help="Show past digest log entries"),
    source: str | None = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
    trends_flag: bool = typer.Option(False, "--trends", help="Include period-over-period trends"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Show a weekly summary comparing current vs previous period."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.digest import build_digest
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    if history:
        rows = db.get_digest_history(period=period, limit=10)
        if format == "json":
            print(json_mod.dumps(rows, indent=2, default=str))
        else:
            from reprompt.output.terminal import render_digest_history

            print(render_digest_history(rows, period), end="")
        return

    stats = db.get_stats()

    # Early guidance when DB is empty (after history check)
    if stats.get("total_prompts", 0) == 0:
        if quiet:
            print("reprompt: no data yet — run reprompt scan")
        elif format == "json":
            print(json_mod.dumps({"error": "no data", "hint": "run reprompt scan"}))
        else:
            console.print(
                "No prompt data yet. Run [bold]reprompt scan[/bold] first to populate the database."
            )
        return

    data = build_digest(db, period=period, source=source)

    if quiet:
        print(data["summary"])
        return

    if format == "json":
        print(json_mod.dumps(data, indent=2, default=str))
    else:
        from reprompt.output.terminal import render_digest

        print(render_digest(data), end="")
        _show_hint(db, "digest")

    if trends_flag:
        from reprompt.core.trends import compute_trends
        from reprompt.output.terminal import render_trends

        trends_data = compute_trends(db, period="7d", n_windows=4, source=source)
        if format == "json":
            print(json_mod.dumps(trends_data, indent=2, default=str))
        else:
            print(render_trends(trends_data), end="")

    if copy:
        _copy_to_clip(json_mod.dumps(data, indent=2, default=str), quiet=(format == "json"))


@app.command(rich_help_panel="Setup")
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


@app.command("install-hook", rich_help_panel="Setup")
def install_hook(
    source: str = typer.Option("claude-code", help="AI tool to install hook for"),
    with_digest: bool = typer.Option(
        False, "--with-digest", help="Also register digest summary hook"
    ),  # noqa: E501
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
        scan_hook_exists = any(
            isinstance(h, dict) and h.get("command") == hook_command for h in stop_hooks
        )
        if scan_hook_exists:
            console.print("Hook already registered in Claude Code settings.")
            if not with_digest:
                return
        else:
            stop_hooks.append(hook_entry)

        # Optionally also register digest --quiet hook
        if with_digest:
            digest_command = "reprompt digest --quiet"
            digest_entry = {"type": "command", "command": digest_command}
            already_has_digest = any(
                isinstance(h, dict) and h.get("command") == digest_command for h in stop_hooks
            )
            if not already_has_digest:
                stop_hooks.append(digest_entry)

        import json

        settings_path.write_text(json.dumps(settings_data, indent=2) + "\n")
        console.print("[green]Hook registered in ~/.claude/settings.json[/green]")
        console.print("reprompt will automatically scan when Claude Code sessions end.")
    else:
        console.print(f"[yellow]Hook installation for '{source}' not yet supported[/yellow]")


@app.command("install-extension", rich_help_panel="Setup")
def install_extension(
    browser: str = typer.Option("chrome", help="Browser: chrome, chromium, firefox"),
    extension_id: str = typer.Option(
        "", "--extension-id", help="Chrome extension ID (overrides default)"
    ),
) -> None:
    """Register Native Messaging host for the browser extension."""
    import json as json_mod

    from reprompt.bridge.manifest import (
        CHROME_EXTENSION_ID,
        CHROME_STORE_URL,
        generate_chrome_manifest,
        generate_firefox_manifest,
        get_manifest_dir,
        get_manifest_filename,
    )

    # Find the host script path
    host_script = _create_host_wrapper()

    # Generate manifest
    if browser in ("chrome", "chromium"):
        if not extension_id:
            extension_id = CHROME_EXTENSION_ID
        manifest = generate_chrome_manifest(str(host_script), extension_id)
    elif browser == "firefox":
        manifest = generate_firefox_manifest(str(host_script))
    else:
        console.print(f"[red]Unknown browser: {browser}. Use chrome, chromium, or firefox.[/red]")
        raise typer.Exit(1)

    # Write manifest
    try:
        manifest_dir = get_manifest_dir(browser)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / get_manifest_filename()
    manifest_path.write_text(json_mod.dumps(manifest, indent=2))

    console.print("[bold green]Native messaging host registered![/bold green]")
    console.print(f"  Browser:  {browser}")
    console.print(f"  Manifest: {manifest_path}")
    console.print(f"  Host:     {host_script}")
    if browser in ("chrome", "chromium"):
        console.print(f"\n  Install extension: {CHROME_STORE_URL}")


def _create_host_wrapper() -> Path:
    """Create a shell wrapper script that launches the Python host."""
    import stat
    import sys as sys_mod

    wrapper_dir = Path.home() / ".config" / "reprompt"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = wrapper_dir / "reprompt-bridge-host"

    # Find the Python executable that has reprompt installed
    python_path = sys_mod.executable

    wrapper_path.write_text(f'#!/bin/sh\nexec "{python_path}" -u -m reprompt.bridge.host\n')
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IEXEC)
    return wrapper_path


@app.command("extension-status", rich_help_panel="Setup")
def extension_status() -> None:
    """Check browser extension connection status."""
    from reprompt.bridge.manifest import (
        CHROME_STORE_URL,
        get_manifest_dir,
        get_manifest_filename,
    )
    from reprompt.config import Settings
    from reprompt.storage.db import PromptDB

    settings = Settings()

    # Check manifest registration
    registered_browsers: list[str] = []
    for browser in ("chrome", "chromium", "firefox"):
        try:
            manifest_dir = get_manifest_dir(browser)
            manifest_path = manifest_dir / get_manifest_filename()
            if manifest_path.exists():
                registered_browsers.append(browser)
        except ValueError:
            continue

    if registered_browsers:
        console.print(f"[green]Registered:[/green] {', '.join(registered_browsers)}")
    else:
        console.print(
            "[yellow]Not registered.[/yellow] Run [bold]reprompt install-extension[/bold]."
        )
        console.print(f"  Chrome Web Store: {CHROME_STORE_URL}")

    # Check DB for extension-sourced prompts
    db = PromptDB(settings.db_path)
    conn = db._conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM prompts WHERE source LIKE '%-ext'"
        ).fetchone()
        ext_count = row["cnt"] if row else 0
    finally:
        conn.close()

    console.print(f"  Extension prompts: {ext_count}")

    # Check last sync
    from reprompt.bridge.handler import _get_last_sync

    last_sync = _get_last_sync(db)
    if last_sync:
        console.print(f"  Last sync:         {last_sync}")
    else:
        console.print("  Last sync:         never")


@app.command(rich_help_panel="Setup")
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Generate a .reprompt.toml config file in the current directory.

    Creates a starter config with all lint rules documented and commented.
    Use this to customize reprompt for your project or CI pipeline.

    Examples:

        reprompt init                     # create .reprompt.toml

        reprompt init --force             # overwrite existing config
    """
    config_path = Path.cwd() / ".reprompt.toml"

    if config_path.exists() and not force:
        console.print(
            f"[yellow]{config_path.name} already exists.[/yellow]"
            " Use [bold]--force[/bold] to overwrite."
        )
        raise typer.Exit(1)

    config_content = """\
# reprompt configuration
# Docs: https://github.com/reprompt-dev/reprompt
#
# This file configures `reprompt lint` rules and CI thresholds.
# Place in your project root — reprompt walks up from CWD to find it.
# Alternatively, add [tool.reprompt.lint] to pyproject.toml.

[lint]
# Fail `reprompt lint` if average prompt score < threshold (0 = disabled)
# Useful for CI: reprompt lint --score-threshold reads this value
# score-threshold = 50

# Target model for model-specific rules (claude, gpt, gemini)
# Enables rules like "prefer XML tags" (Claude) or "avoid XML tags" (GPT)
# model = "claude"

# Token budget — warn when prompts exceed this limit (0 = disabled)
# max-tokens = 4096

[lint.rules]
# min-length: error if prompt < N chars (0 = disabled)
min-length = 20

# short-prompt: warning if prompt < N chars (0 = disabled)
short-prompt = 40

# vague-prompt: error on vague prompts like "fix it" (false = disabled)
vague-prompt = true

# debug-needs-reference: warning if debug prompt lacks file reference (false = disabled)
debug-needs-reference = true

# file-extensions: extensions recognized as file references
# file-extensions = [".py", ".ts", ".js", ".go", ".rs", ".java", ".rb", ".cpp", ".c"]
"""

    config_path.write_text(config_content)
    console.print(f"[green]Created[/green] {config_path.name}")
    console.print("  Edit rules, then run [bold]reprompt lint[/bold] to verify.")


@app.command(rich_help_panel="Setup")
def feedback() -> None:
    """Open the feedback form — share your experience, ideas, or suggestions.

    Opens a GitHub issue template in your browser. No account required to view,
    but you'll need a GitHub account to submit.

    Examples:

        reprompt feedback
    """
    import webbrowser

    from reprompt.core.suggestions import FEEDBACK_URL

    console.print(
        "\n  [bold]We'd love to hear from you![/bold]\n  Opening feedback form in your browser...\n"
    )
    opened = webbrowser.open(FEEDBACK_URL)
    if not opened:
        console.print(f"  [dim]Could not open browser. Visit:[/dim]\n  {FEEDBACK_URL}\n")


@app.command(rich_help_panel="Analyze")
def projects(
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Compare prompt quality across projects.

    Shows per-project breakdown: sessions, prompts, quality scores,
    efficiency, focus, and frustration signals.

    Examples:

        reprompt projects                          # all projects

        reprompt projects --source claude-code      # filter by source

        reprompt projects --json                   # machine-readable
    """
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.output.projects_terminal import render_projects_table
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    project_data = db.get_project_summary(source=source)

    if json_output:
        print(json_mod.dumps(project_data, indent=2, default=str))
    else:
        output = render_projects_table(project_data)
        print(output)

    if copy:
        if json_output:
            _copy_to_clip(json_mod.dumps(project_data, indent=2, default=str), quiet=True)
        else:
            _copy_to_clip(output)

    _show_hint(db, "projects", json_output=json_output)


@app.command(rich_help_panel="Analyze")
def sessions(
    last: int = typer.Option(10, "--last", help="Show N most recent sessions"),
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    detail: str = typer.Option(None, "--detail", help="Deep-dive into a session ID"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Session quality overview: composite scores, frustration signals, trends."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.output.sessions_terminal import render_session_detail, render_sessions_table
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    if detail:
        # Single session detail view
        all_sessions = db.get_sessions_with_quality(limit=500)
        match = next((s for s in all_sessions if s.get("session_id") == detail), None)
        if not match:
            # Try prefix match
            match = next(
                (s for s in all_sessions if (s.get("session_id") or "").startswith(detail)),
                None,
            )
        if not match:
            typer.echo(f"Session '{detail}' not found.")
            raise typer.Exit(1)
        if json_output:
            typer.echo(json_mod.dumps(match, indent=2, default=str))
        else:
            typer.echo(render_session_detail(match), nl=False)
    else:
        data = db.get_sessions_with_quality(limit=last, source=source)
        if json_output:
            typer.echo(json_mod.dumps(data, indent=2, default=str))
        else:
            typer.echo(render_sessions_table(data), nl=False)
            _show_hint(db, "sessions")

    if copy:
        if detail:
            copy_text = json_mod.dumps(match, indent=2, default=str)  # type: ignore[possibly-undefined]
        else:
            copy_text = json_mod.dumps(data, indent=2, default=str)  # type: ignore[possibly-undefined]
        _copy_to_clip(copy_text, quiet=json_output)


@app.command(rich_help_panel="Analyze")
def patterns(
    last: int = typer.Option(500, "--last", help="Analyze N most recent prompts"),
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Discover your personal prompt weaknesses and recurring gaps."""
    import json as json_mod
    from dataclasses import asdict

    from reprompt.config import Settings
    from reprompt.core.patterns import analyze_patterns
    from reprompt.output.patterns_terminal import render_patterns
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    report = analyze_patterns(db, source=source, limit=last)

    if json_output:
        typer.echo(json_mod.dumps(asdict(report), indent=2, default=str))
    else:
        typer.echo(render_patterns(report), nl=False)
        _show_hint(db, "patterns", json_output=json_output)

    if copy:
        copy_text = json_mod.dumps(asdict(report), indent=2, default=str)
        _copy_to_clip(copy_text, quiet=json_output)


@app.command(rich_help_panel="Analyze")
def repetition(
    last: int = typer.Option(500, "--last", help="Analyze N most recent unique prompts"),
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
) -> None:
    """Detect recurring prompts across different sessions."""
    import json as json_mod
    from dataclasses import asdict

    from reprompt.config import Settings
    from reprompt.core.repetition import analyze_repetition
    from reprompt.output.repetition_terminal import render_repetition_report
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    report = analyze_repetition(db, source=source, limit=last)

    if json_output:
        typer.echo(json_mod.dumps(asdict(report), indent=2, default=str))
    else:
        typer.echo(render_repetition_report(report), nl=False)
        _show_hint(db, "repetition")

    if copy:
        copy_text = json_mod.dumps(asdict(report), indent=2, default=str)
        _copy_to_clip(copy_text, quiet=json_output)


@app.command(rich_help_panel="Analyze")
def agent(
    last: int = typer.Option(5, "--last", help="Analyze N most recent sessions"),
    source: str = typer.Option(
        None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
    loops_only: bool = typer.Option(False, "--loops-only", help="Show only error loops"),
) -> None:
    """Analyze agent workflow: error loops, tool patterns, session efficiency."""
    from reprompt.config import Settings
    from reprompt.core.agent import analyze_sessions
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

    sessions = _resolve_distill_sessions(db, session_id=None, last=last, source=source)
    if not sessions:
        if json_output:
            typer.echo("{}")
        else:
            typer.echo(
                "No agent sessions found. Run [bold]reprompt scan[/bold] to import sessions first."
            )
        return

    conversations = []
    for file_path, adapter_source, resolved_sid in sessions:
        conv = _load_conversation(file_path, adapter_source, db, resolved_sid)
        if conv is not None:
            conversations.append(conv)
        if len(conversations) >= last:
            break

    if not conversations:
        if json_output:
            typer.echo("{}")
        else:
            typer.echo("Could not load any sessions.")
        return

    agg = analyze_sessions(conversations)

    if json_output:
        import json as json_mod
        from dataclasses import asdict

        typer.echo(json_mod.dumps(asdict(agg), indent=2, default=str))
    elif loops_only:
        from reprompt.output.agent_terminal import render_loops_only

        typer.echo(render_loops_only(agg), nl=False)
    else:
        from reprompt.output.agent_terminal import render_agent_report

        typer.echo(render_agent_report(agg), nl=False)
        _show_hint(db, "agent")

    if copy:
        import json as json_mod
        from dataclasses import asdict

        copy_text = json_mod.dumps(asdict(agg), indent=2, default=str)
        _copy_to_clip(copy_text, quiet=json_output)


# Register late commands (template, wrapped, telemetry) after all @app.command()
# so help panels appear in order: Analyze → Optimize → Manage → Setup
_register_late_commands()
