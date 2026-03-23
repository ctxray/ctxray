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

app = typer.Typer(
    name="reprompt",
    help="Discover, analyze, and evolve your best prompts from AI coding sessions.",
    no_args_is_help=True,
)
console = Console()


def _register_free_tier_commands() -> None:
    """Register Free tier commands (wrapped + telemetry) directly."""
    from reprompt.commands.telemetry import telemetry_app
    from reprompt.commands.wrapped import wrapped

    app.command()(wrapped)
    app.add_typer(telemetry_app, name="telemetry", help="Manage anonymous telemetry")


_register_free_tier_commands()


def _load_plugins() -> None:
    """Auto-discover and load reprompt plugins (e.g. reprompt-pro)."""
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="reprompt.plugins")
        for ep in eps:
            try:
                register_fn = ep.load()
                register_fn(app)
            except Exception:
                pass  # plugin load failure should never break core CLI
    except Exception:
        pass


_load_plugins()


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
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Skip auto-report after scan"),
) -> None:
    """Scan AI tool sessions for prompts."""
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

    # Suggest install-hook if not already set up
    db = PromptDB(settings.db_path)
    stats = db.get_stats()
    if stats.get("total_prompts", 0) > 0:
        hook_installed = (Path.home() / ".claude" / "settings.json").exists() and _hook_registered()
        if not hook_installed:
            console.print(
                "\n[dim]Tip: Run [bold]reprompt install-hook[/bold] to auto-scan "
                "after every Claude Code session.[/dim]"
            )

    # Next steps for new users (show once, on first scan with data)
    if result.new_stored > 0 and stats.get("total_prompts", 0) <= result.new_stored + 10:
        console.print("\n[bold]Try next:[/bold]")
        console.print('  reprompt score [dim]"your prompt"[/dim]   — instant quality score')
        console.print("  reprompt library              — see your prompt patterns")
        console.print("  reprompt insights             — personal analysis")


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


@app.command(name="import")
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


@app.command()
def report(
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    html: bool = typer.Option(False, "--html", help="Generate interactive HTML dashboard"),
    output: str = typer.Option("", "--output", "-o", help="Output file path (for --html)"),
    top: int = typer.Option(20, help="Number of top terms to show"),
    clusters: int = typer.Option(0, "--clusters", help="Number of clusters (0 = auto-select)"),
    source: str = typer.Option(
        "", "--source", "-s", help="Filter by source (e.g. chatgpt-ext, claude-ext, claude-code)"
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

        from reprompt.core.effectiveness import effectiveness_stars

        # Determine if any pattern has effectiveness data
        has_eff = any(p.get("effectiveness_avg") is not None for p in patterns)

        table = Table(title="Prompt Library")
        table.add_column("#", style="dim", width=4)
        table.add_column("Pattern", max_width=50)
        table.add_column("Uses", justify="right")
        table.add_column("Category")
        if has_eff:
            table.add_column("Eff", justify="right")

        for i, p in enumerate(patterns, 1):
            pattern_text = str(p.get("pattern_text", ""))
            display = (pattern_text[:50] + "...") if len(pattern_text) > 50 else pattern_text
            row = [
                str(i),
                display,
                str(p.get("frequency", 0)),
                str(p.get("category", "")),
            ]
            if has_eff:
                avg = p.get("effectiveness_avg")
                if avg is not None:
                    row.append(f"{avg:.2f} {effectiveness_stars(avg)}")
                else:
                    row.append("—")
            table.add_row(*row)
        console.print(table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term (case-insensitive)"),
    limit: int = typer.Option(20, help="Maximum results to show"),
    source: str = typer.Option(
        "", "--source", "-s", help="Filter by source (e.g. chatgpt-ext, claude-ext, claude-code)"
    ),
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


@app.command()
def recommend(
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
) -> None:
    """Suggest better prompts based on your history and effectiveness."""
    from reprompt.config import Settings
    from reprompt.core.recommend import compute_recommendations
    from reprompt.output.terminal import render_recommendations
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    data = compute_recommendations(db)

    if format == "json":
        import json as json_mod

        print(json_mod.dumps(data, indent=2, default=str))
    else:
        print(render_recommendations(data), end="")


@app.command("merge-view")
def merge_view(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    limit: int = typer.Option(0, "--limit", help="Max clusters to show (0 = all)"),
) -> None:
    """Show clusters of similar prompts you keep rewriting."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.merge_view import build_clusters
    from reprompt.output.terminal import render_merge_view
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    all_prompts = db.get_all_prompts()

    unique = [p for p in all_prompts if p.get("duplicate_of") is None]
    texts = [p["text"] for p in unique]
    timestamps = [p.get("timestamp", "") for p in unique]

    clusters = build_clusters(texts, timestamps, threshold=settings.dedup_threshold)

    if limit > 0:
        clusters = clusters[:limit]

    total_clustered = sum(c["size"] for c in clusters)
    data = {
        "clusters": clusters,
        "summary": {
            "total_clustered_prompts": total_clustered,
            "cluster_count": len(clusters),
            "reduction_potential": f"{total_clustered} → {len(clusters)}",
        },
    }

    if json_output:
        print(json_mod.dumps(data, indent=2, default=str))
    else:
        print(render_merge_view(data), end="")


@app.command()
def save(
    text: str = typer.Argument(..., help="Prompt text to save as template"),
    name: str = typer.Option("", "--name", "-n", help="Template name (auto-generated if omitted)"),
    category: str = typer.Option(
        "", "--category", "-c", help="Category (auto-detected if omitted)"
    ),
) -> None:
    """Save a prompt as a reusable template."""
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
    typer.echo(f"Saved template '{result['name']}' (category: {result['category']})")


@app.command()
def templates(
    category: str = typer.Option("", "--category", "-c", help="Filter by category"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List your saved prompt templates."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.output.terminal import render_templates
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    items = db.list_templates(category=category or None)

    if json_output:
        print(json_mod.dumps(items, indent=2, default=str))
    else:
        print(render_templates(items, category_filter=category or None), end="")


@app.command()
def style(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show your personal prompting style fingerprint."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.library import categorize_prompt
    from reprompt.core.style import compute_style
    from reprompt.output.terminal import render_style
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    rows = db.get_all_prompts()
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


@app.command()
def use(
    name: str = typer.Argument(..., help="Template name to use"),
    variables: list[str] = typer.Argument(None, help="Variables as key=value pairs"),
) -> None:
    """Use a saved template with variable substitution."""
    from reprompt.config import Settings
    from reprompt.core.templates import extract_variables, render_template
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    template = db.get_template(name)

    if template is None:
        console.print(f"[red]Template '{name}' not found.[/red]")
        console.print("Run [bold]reprompt templates[/bold] to see available templates.")
        raise typer.Exit(1)

    text = template["text"]

    # Parse key=value pairs
    var_dict: dict[str, str] = {}
    for v in variables or []:
        if "=" in v:
            key, val = v.split("=", 1)
            var_dict[key] = val

    rendered = render_template(text, var_dict)

    # Show unfilled variables as hint
    remaining = extract_variables(rendered)
    if remaining:
        console.print(f"[dim]Unfilled variables: {', '.join(remaining)}[/dim]")

    console.print(rendered)
    db.increment_template_usage(name)


@app.command()
def lint(
    source: str = typer.Option(None, help="Adapter to scan (claude-code, aider, gemini, etc.)"),
    path: str = typer.Option(None, help="Path to scan for session files"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON"),
    fail_on_warning: bool = typer.Option(False, "--strict", help="Exit 1 on warnings too"),
) -> None:
    """Check prompt quality against lint rules.

    Scans session history and checks each prompt for quality issues:
    - min-length: prompts under 20 chars
    - short-prompt: prompts under 40 chars (warning)
    - vague-prompt: overly vague prompts like "fix it"
    - debug-needs-reference: debug prompts without file/function references
    """
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.lint import format_lint_results, lint_prompts
    from reprompt.core.pipeline import get_adapters
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)

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

    violations = lint_prompts(texts)

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
        print(json_mod.dumps(data, indent=2))
    else:
        print(format_lint_results(violations, len(texts)))

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    if errors or (fail_on_warning and warnings):
        raise typer.Exit(1)


@app.command()
def score(
    text: str = typer.Argument(..., help="Prompt text to score"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Score a prompt using research-backed analysis."""
    from reprompt.core.extractors import extract_features
    from reprompt.core.scorer import score_prompt

    dna = extract_features(text, source="manual", session_id="score-cli")
    breakdown = score_prompt(dna)
    dna.overall_score = breakdown.total

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
            "context_specificity": dna.context_specificity,
            "ambiguity_score": dna.ambiguity_score,
            "suggestions": [
                {
                    "category": s.category,
                    "paper": s.paper,
                    "message": s.message,
                    "impact": s.impact,
                }
                for s in breakdown.suggestions
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
            "suggestions": [
                {
                    "category": s.category,
                    "paper": s.paper,
                    "message": s.message,
                    "impact": s.impact,
                }
                for s in breakdown.suggestions
            ],
        }
        typer.echo(render_score(data))


@app.command()
def compress(
    text: str = typer.Argument(..., help="Prompt text to compress"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy compressed text to clipboard"),
) -> None:
    """Compress a prompt by removing filler words and simplifying phrases."""
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
        from reprompt.sharing.clipboard import copy_to_clipboard

        if copy_to_clipboard(result.compressed):
            if not json_output:
                typer.echo("  Copied to clipboard!")
        else:
            typer.echo("  Could not copy to clipboard (xclip/xsel not found)", err=True)


@app.command()
def distill(
    session_id: str = typer.Argument(None, help="Session ID to distill"),
    last: int = typer.Option(1, "--last", help="Distill the N most recent sessions"),
    source: str = typer.Option(None, "--source", help="Filter by adapter name"),
    summary: bool = typer.Option(False, "--summary", help="Show compressed summary"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    copy: bool = typer.Option(False, "--copy", help="Copy result to clipboard"),
    threshold: float = typer.Option(0.3, "--threshold", help="Importance cutoff (0.0-1.0)"),
) -> None:
    """Distill a conversation to its most important turns."""
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
    for file_path, adapter_source, resolved_sid in sessions:
        conv = _load_conversation(file_path, adapter_source, db, resolved_sid)
        if conv is None:
            continue
        result = distill_conversation(conv, threshold=threshold)
        if summary:
            result.summary = generate_summary(result)
        results.append(result)

    if not results:
        if json_output:
            typer.echo("[]")
        else:
            typer.echo("Could not load any sessions.")
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

    if copy:
        from reprompt.sharing.clipboard import copy_to_clipboard

        if summary:
            copy_text = "\n---\n".join(r.summary or "" for r in results)
        else:
            copy_parts = []
            for result in results:
                for turn in result.filtered_turns:
                    prefix = "User" if turn.role == "user" else "Assistant"
                    copy_parts.append(f"[{prefix}] {turn.text}")
            copy_text = "\n\n".join(copy_parts)

        if copy_to_clipboard(copy_text):
            if not json_output:
                typer.echo("  Copied to clipboard!")
        else:
            typer.echo("  Could not copy to clipboard (xclip/xsel not found)", err=True)


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
            query += " ORDER BY processed_at DESC LIMIT ?"
            params.append(str(last))
            rows = conn.execute(query, params).fetchall()
            return [(r["file_path"], r["source"], None) for r in rows]
    finally:
        conn.close()


def _load_conversation(
    file_path: str, adapter_source: str, db: PromptDB,
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


@app.command()
def compare(
    prompt_a: str = typer.Argument(..., help="First prompt"),
    prompt_b: str = typer.Argument(..., help="Second prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Compare two prompts side by side using Prompt DNA analysis."""
    from reprompt.core.extractors import extract_features
    from reprompt.core.prompt_dna import PromptDNA
    from reprompt.core.scorer import ScoreBreakdown, score_prompt

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

    result = {
        "prompt_a": _build_data(dna_a, score_a),
        "prompt_b": _build_data(dna_b, score_b),
    }

    if json_output:
        import json as json_mod

        typer.echo(json_mod.dumps(result, indent=2))
    else:
        from reprompt.output.terminal import render_compare

        typer.echo(render_compare(result))


@app.command()
def insights(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show research-backed insights about your prompting patterns."""
    from reprompt.config import Settings
    from reprompt.core.insights import compute_insights
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    all_features = db.get_all_features()
    result = compute_insights(all_features)

    if json_output:
        import json as json_mod

        typer.echo(json_mod.dumps(result, indent=2))
    else:
        from reprompt.output.terminal import render_insights

        typer.echo(render_insights(result))


@app.command()
def privacy(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show where your prompts went and how they may be used."""
    import json as json_mod

    from reprompt.config import Settings
    from reprompt.core.privacy import compute_privacy_summary
    from reprompt.output.terminal import render_privacy
    from reprompt.storage.db import PromptDB

    settings = Settings()
    db = PromptDB(settings.db_path)
    all_prompts = db.get_all_prompts()

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


@app.command()
def digest(
    period: str = typer.Option("7d", help="Comparison window: 7d, 14d, 30d"),
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    quiet: bool = typer.Option(False, "--quiet", help="One-line summary (for hooks/cron)"),
    history: bool = typer.Option(False, "--history", help="Show past digest log entries"),
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

    data = build_digest(db, period=period)

    if quiet:
        print(data["summary"])
        return

    if format == "json":
        print(json_mod.dumps(data, indent=2, default=str))
    else:
        from reprompt.output.terminal import render_digest

        print(render_digest(data), end="")


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


@app.command("install-extension")
def install_extension(
    browser: str = typer.Option("chrome", help="Browser: chrome, chromium, firefox"),
    extension_id: str = typer.Option(
        "", "--extension-id", help="Chrome extension ID (required for chrome/chromium)"
    ),
) -> None:
    """Register Native Messaging host for the browser extension."""
    import json as json_mod

    from reprompt.bridge.manifest import (
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
            console.print(
                "[yellow]No --extension-id provided. "
                "You'll need to update the manifest after installing the extension.[/yellow]"
            )
            extension_id = "PLACEHOLDER_EXTENSION_ID"
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
    if extension_id == "PLACEHOLDER_EXTENSION_ID":
        console.print(
            "\n[yellow]Next: install the reprompt extension, then re-run with "
            "--extension-id to update the manifest.[/yellow]"
        )


def _create_host_wrapper() -> Path:
    """Create a shell wrapper script that launches the Python host."""
    import stat
    import sys as sys_mod

    wrapper_dir = Path.home() / ".config" / "reprompt"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = wrapper_dir / "reprompt-bridge-host"

    # Find the Python executable that has reprompt installed
    python_path = sys_mod.executable

    wrapper_path.write_text(f"#!/bin/sh\nexec {python_path} -u -m reprompt.bridge.host\n")
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IEXEC)
    return wrapper_path


@app.command("extension-status")
def extension_status() -> None:
    """Check browser extension connection status."""
    from reprompt.bridge.manifest import (
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
