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


@app.command()
def report(
    format: str = typer.Option("terminal", help="Output format: terminal, json"),
    html: bool = typer.Option(False, "--html", help="Generate interactive HTML dashboard"),
    output: str = typer.Option("", "--output", "-o", help="Output file path (for --html)"),
    top: int = typer.Option(20, help="Number of top terms to show"),
) -> None:
    """Generate analytics report."""
    from reprompt.config import Settings
    from reprompt.core.pipeline import build_report_data

    settings = Settings()
    data = build_report_data(settings=settings)

    if html:
        import webbrowser
        from pathlib import Path

        from reprompt.core.recommend import compute_recommendations
        from reprompt.core.trends import compute_trends
        from reprompt.output.html_report import render_html_dashboard
        from reprompt.storage.db import PromptDB

        db = PromptDB(settings.db_path)
        trends_data = compute_trends(db, period="7d", n_windows=6)
        recommend_data = compute_recommendations(db)

        html_content = render_html_dashboard(data, trends_data, recommend_data)
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

    def _build_data(
        dna: PromptDNA, sc: ScoreBreakdown
    ) -> dict[str, object]:
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
