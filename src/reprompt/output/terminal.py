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

    # Hot Phrases (TF-IDF n-grams)
    if data.get("top_terms"):
        terms_table = Table(title="Hot Phrases (TF-IDF)")
        terms_table.add_column("#", style="dim", width=4)
        terms_table.add_column("Phrase", max_width=30)
        terms_table.add_column("TF-IDF", justify="right")
        terms_table.add_column("Docs", justify="right")
        for i, t in enumerate(data["top_terms"][:10], 1):
            terms_table.add_row(str(i), t["term"], f"{t['tfidf_avg']:.3f}", str(t.get("df", "")))
        console.print(terms_table)

    # Top patterns table
    if data["top_patterns"]:
        table = Table(title="Top Prompt Patterns")
        table.add_column("#", style="dim", width=4)
        table.add_column("Pattern", max_width=40)
        table.add_column("Count", justify="right")
        table.add_column("Category")
        for i, p in enumerate(data["top_patterns"][:10], 1):
            pat = p["pattern_text"]
            pat_display = pat[:40] + "..." if len(pat) > 40 else pat
            table.add_row(str(i), pat_display, str(p["frequency"]), p["category"])
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

    # Prompt Clusters (K-means)
    if data.get("clusters"):
        console.print("\n[bold]Prompt Clusters (K-means)[/bold]")
        for c in data["clusters"]:
            sample = c["sample"][:80] + "..." if len(c["sample"]) > 80 else c["sample"]
            console.print(f'  Cluster {c["cluster_id"] + 1} ({c["size"]} prompts):  "{sample}"')

    console.print("\nRun `reprompt library` to see your reusable prompt collection")
    console.print("Run `reprompt trends` to see your prompt evolution over time")

    return buf.getvalue()


def render_trends(data: dict[str, Any]) -> str:
    """Render prompt evolution trends to a string using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]reprompt trends — Prompt Evolution[/bold]")
    console.print("=" * 40)

    windows = data.get("windows", [])
    if not windows:
        console.print("No data available.")
        return buf.getvalue()

    table = Table(title=f"Period: {data.get('period', '7d')}")
    table.add_column("Period", min_width=16)
    table.add_column("Prompts", justify="right")
    table.add_column("Avg Len", justify="right")
    table.add_column("Vocab", justify="right")
    table.add_column("Specificity", justify="right")

    for w in windows:
        label = w.get("window_label", "")
        count = str(w.get("prompt_count", 0))
        avg_len = f"{w.get('avg_length', 0):.0f}"
        vocab = str(w.get("vocab_size", 0))

        spec = w.get("specificity_score", 0)
        delta_pct = w.get("specificity_pct", 0)
        if delta_pct > 0:
            spec_str = f"{spec:.2f}  [green]↑ +{delta_pct}%[/green]"
        elif delta_pct < 0:
            spec_str = f"{spec:.2f}  [red]↓ {delta_pct}%[/red]"
        else:
            spec_str = f"{spec:.2f}"

        table.add_row(label, count, avg_len, vocab, spec_str)

    console.print(table)

    # Insights
    insights = data.get("insights", [])
    if insights:
        console.print("\n[bold]Insights[/bold]")
        for insight in insights:
            console.print(f"  • {insight}")

    # Category distribution for latest window with data
    active = [w for w in windows if w.get("prompt_count", 0) > 0]
    if active:
        latest = active[-1]
        cats = latest.get("category_distribution", {})
        if cats:
            console.print("\n[bold]Category Distribution (latest period)[/bold]")
            total = sum(cats.values()) or 1
            for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
                pct = int(count / total * 100)
                bar_len = int(count / total * 20)
                bar = "\u2588" * bar_len
                console.print(f"  {cat:<12} {bar} {pct}%")

    return buf.getvalue()


def render_recommendations(data: dict[str, Any]) -> str:
    """Render prompt recommendations to a string using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]reprompt recommend — Prompt Improvement Tips[/bold]")
    console.print("=" * 40)

    total = data.get("total_prompts", 0)
    if total == 0:
        console.print("No prompts found. Run [bold]reprompt scan[/bold] first.")
        return buf.getvalue()

    # Best prompts to reuse
    best = data.get("best_prompts", [])
    if best:
        table = Table(title="Your Best Prompts (reuse these)")
        table.add_column("#", style="dim", width=4)
        table.add_column("Prompt", max_width=50)
        table.add_column("Score", justify="right", width=6)
        table.add_column("Project", width=12)
        for i, p in enumerate(best[:5], 1):
            text = p["text"]
            display = text[:50] + "..." if len(text) > 50 else text
            table.add_row(str(i), display, f"{p['effectiveness']:.2f}", p.get("project", ""))
        console.print(table)

    # Effectiveness by category
    cat_eff = data.get("category_effectiveness", {})
    if cat_eff:
        console.print("\n[bold]Effectiveness by Category[/bold]")
        sorted_cats = sorted(cat_eff.items(), key=lambda x: -x[1])
        for cat, score in sorted_cats:
            bar_len = int(score * 20)
            bar = "\u2588" * bar_len
            color = "green" if score >= 0.5 else "yellow" if score >= 0.3 else "red"
            console.print(f"  {cat:<12} {bar} [{color}]{score:.2f}[/{color}]")

    # Short prompt alerts
    alerts = data.get("short_prompt_alerts", [])
    if alerts:
        console.print("\n[bold]Prompts to Improve[/bold] (short + low effectiveness)")
        for a in alerts:
            console.print(f'  [red]x[/red] "{a["text"]}" ({a["char_count"]} chars)')

    # Specificity upgrade tips
    tips = data.get("specificity_tips", [])
    if tips:
        console.print("\n[bold]How to Write Better Prompts[/bold]")
        for t in tips:
            console.print(f'  [dim]Instead of:[/dim] "{t["original"]}"')
            console.print(f"  [green]Tip:[/green] {t['tip']}")
            console.print()

    # Category tips
    for tip in data.get("category_tips", []):
        console.print(f"  [yellow]![/yellow] {tip}")

    # Overall tips
    for tip in data.get("overall_tips", []):
        console.print(f"  [cyan]*[/cyan] {tip}")

    return buf.getvalue()


def render_merge_view(data: dict[str, Any]) -> str:
    """Render merge-view clusters to a string using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]reprompt merge-view — Similar Prompt Clusters[/bold]")
    console.print("=" * 40)

    clusters = data.get("clusters", [])
    summary = data.get("summary", {})

    if not clusters:
        console.print("No similar prompt clusters found.")
        console.print("Run [bold]reprompt scan[/bold] to index more sessions.")
        return buf.getvalue()

    total = summary.get("total_clustered_prompts", 0)
    count = summary.get("cluster_count", 0)
    console.print(
        f"Found [bold]{count}[/bold] clusters of similar prompts "
        f"([bold]{total}[/bold] prompts total)\n"
    )

    for c in clusters:
        console.print(f"[bold]Cluster {c['id'] + 1}: {c['name']}[/bold] ({c['size']} prompts)")
        canon = c["canonical"]
        console.print(
            f'  [green]★[/green] "{canon["text"]}"     [dim]score: {canon["score"]:.2f}[/dim]'
        )
        for m in c.get("members", []):
            console.print(f'    "{m["text"]}"     [dim]{m.get("timestamp", "")}[/dim]')
        console.print("  [dim]→ Reuse the ★ prompt instead of writing a new one[/dim]\n")

    console.print(f"[bold]Summary:[/bold] {total} prompts could be reduced to {count} templates.")
    if count > 0:
        console.print("Run [bold]reprompt save[/bold] to save ★ prompts as reusable templates.")

    return buf.getvalue()
