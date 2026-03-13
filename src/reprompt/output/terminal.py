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


def render_templates(templates: list[dict[str, Any]], category_filter: str | None = None) -> str:
    """Render prompt templates list to a string using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    title = "reprompt templates"
    if category_filter:
        title += f" — {category_filter}"
    console.print(f"\n[bold]{title}[/bold]")
    console.print("=" * 40)

    if not templates:
        console.print("No templates saved yet.")
        console.print('Run [bold]reprompt save "your prompt"[/bold] to save one.')
        return buf.getvalue()

    console.print(f"Your Prompt Templates ({len(templates)} saved)\n")

    table = Table()
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", max_width=20)
    table.add_column("Category", width=10)
    table.add_column("Text", max_width=35)
    table.add_column("Used", justify="right", width=5)

    for i, t in enumerate(templates, 1):
        text = t["text"]
        display = text[:35] + "..." if len(text) > 35 else text
        table.add_row(
            str(i),
            t["name"],
            t.get("category", "other"),
            display,
            str(t.get("usage_count", 0)),
        )

    console.print(table)
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


def render_score(breakdown: dict[str, Any]) -> str:
    """Render a prompt score breakdown."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    total = breakdown["total"]
    grade = (
        "Excellent" if total >= 80 else "Good" if total >= 60 else "Fair" if total >= 40 else "Poor"
    )

    console.print(f"\n[bold]Prompt DNA Score: {total:.0f}/100[/bold]  ({grade})")
    console.print("\u2500" * 40)

    # Category bars
    categories = [
        ("Structure", breakdown["structure"], 25),
        ("Context", breakdown["context"], 25),
        ("Position", breakdown["position"], 20),
        ("Repetition", breakdown["repetition"], 15),
        ("Clarity", breakdown["clarity"], 15),
    ]
    for name, cat_score, max_val in categories:
        pct = cat_score / max_val if max_val > 0 else 0
        filled = int(pct * 10)
        bar = "\u2588" * filled + "\u2591" * (10 - filled)
        console.print(f" {name:<12} {bar}  {cat_score:.0f}/{max_val}")

    # Suggestions
    suggestions = breakdown.get("suggestions", [])
    if suggestions:
        console.print(f"\n[bold]Suggestions ({len(suggestions)}):[/bold]")
        for s in suggestions:
            impact_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(s["impact"], "dim")
            console.print(f" [{impact_color}]\u25a0[/{impact_color}] [{s['paper']}] {s['message']}")

    return buf.getvalue()


def render_insights(data: dict[str, Any]) -> str:
    """Render personal prompt insights."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    count = data["prompt_count"]
    if count == 0:
        console.print(
            "\n[dim]No prompt data yet. Run 'reprompt scan' first, then 'reprompt insights'.[/dim]"
        )
        return buf.getvalue()

    console.print(f"\n[bold]Prompt Insights[/bold] (based on {count} prompts)")
    console.print("\u2500" * 40)

    console.print(f"  Average Score:   {data['avg_score']:.0f}/100")
    best = data["best_task_type"]
    worst = data["worst_task_type"]
    console.print(f"  Strongest:       {best['type']} ({best['avg_score']:.0f}/100)")
    console.print(f"  Weakest:         {worst['type']} ({worst['avg_score']:.0f}/100)")

    # Score distribution
    dist = data.get("score_distribution", {})
    if dist:
        console.print("\n[bold]Score Distribution:[/bold]")
        max_count = max(dist.values()) if dist.values() else 1
        for bucket, cnt in dist.items():
            bar_len = int(cnt / max_count * 20) if max_count > 0 else 0
            bar = "\u2588" * bar_len
            console.print(f"  {bucket:>6}  {bar} {cnt}")

    # Research-backed insights
    insights = data.get("insights", [])
    if insights:
        console.print(f"\n[bold]Research-backed Findings ({len(insights)}):[/bold]")
        for i, insight in enumerate(insights, 1):
            impact_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(
                insight["impact"], "dim"
            )
            console.print(
                f"\n  [{impact_color}]{i}. {insight['category'].title()}[/{impact_color}]"
            )
            console.print(f"     {insight['finding']}")
            console.print(f"     {insight['optimal']}")
            console.print(f"     [bold]\u2192 {insight['action']}[/bold]")
            console.print(f"     [dim][{insight['paper']}][/dim]")

    return buf.getvalue()


def render_compare(data: dict[str, Any]) -> str:
    """Render a side-by-side prompt comparison."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]Prompt Comparison[/bold]")

    table = Table()
    table.add_column("Feature", style="dim", min_width=18)
    table.add_column("Prompt A", justify="right")
    table.add_column("Prompt B", justify="right")
    table.add_column("\u0394", justify="right")

    a = data["prompt_a"]
    b = data["prompt_b"]

    rows = [
        ("Score", a["total"], b["total"]),
        ("Word Count", a["word_count"], b["word_count"]),
        ("Structure", a["structure"], b["structure"]),
        ("Context", a["context"], b["context"]),
        ("Position", a["position"], b["position"]),
        ("Repetition", a["repetition"], b["repetition"]),
        ("Clarity", a["clarity"], b["clarity"]),
        ("Specificity", a["context_specificity"], b["context_specificity"]),
        ("Ambiguity", a["ambiguity_score"], b["ambiguity_score"]),
    ]
    for label, va, vb in rows:
        delta = vb - va
        sign = "+" if delta > 0 else ""
        color = "green" if delta > 0 else "red" if delta < 0 else "dim"
        table.add_row(
            label,
            f"{va:.1f}" if isinstance(va, float) else str(va),
            f"{vb:.1f}" if isinstance(vb, float) else str(vb),
            f"[{color}]{sign}{delta:.1f}[/{color}]",
        )

    console.print(table)

    # Winner
    if a["total"] != b["total"]:
        winner = "B" if b["total"] > a["total"] else "A"
        diff = abs(b["total"] - a["total"])
        console.print(f"\n[bold]Prompt {winner} scores {diff:.0f} points higher.[/bold]")

    return buf.getvalue()


def render_digest(data: dict[str, Any]) -> str:
    """Render a weekly digest summary using Rich."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    period = data.get("period", "7d")
    current = data.get("current", {})
    previous = data.get("previous", {})
    count_delta = data.get("count_delta", 0)
    spec_delta = data.get("spec_delta", 0.0)

    console.print(f"\n[bold]reprompt digest — Weekly Summary ({period})[/bold]")
    console.print("=" * 40)

    # Activity
    curr_count = current.get("prompt_count", 0)
    sign = "+" if count_delta > 0 else ""
    count_color = "green" if count_delta > 0 else ("red" if count_delta < 0 else "dim")
    delta_str = f"{sign}{count_delta}"
    console.print(
        f"  Prompts this period:  {curr_count}"
        f"  [{count_color}]({delta_str} vs previous)[/{count_color}]",
        highlight=False,
    )

    curr_spec = current.get("specificity_score", 0.0)
    spec_arrow = "↑" if spec_delta > 0.01 else ("↓" if spec_delta < -0.01 else "→")
    spec_color = "green" if spec_delta > 0.01 else ("red" if spec_delta < -0.01 else "dim")
    spec_delta_str = f"{spec_delta:+.2f}"
    console.print(
        f"  Specificity score:    {curr_spec:.2f}"
        f"  [{spec_color}]{spec_arrow} {spec_delta_str}[/{spec_color}]",
        highlight=False,
    )

    avg_len = current.get("avg_length", 0.0)
    console.print(f"  Avg prompt length:    {avg_len:.0f} chars", highlight=False)

    eff_avg = data.get("eff_avg")
    if eff_avg is not None:
        from reprompt.core.effectiveness import effectiveness_stars

        console.print(
            f"  Session quality:      {eff_avg:.2f} {effectiveness_stars(eff_avg)}",
            highlight=False,
        )

    # Category distribution comparison
    curr_cats = current.get("category_distribution", {})
    prev_cats = previous.get("category_distribution", {})
    if curr_cats:
        console.print("\n[bold]Category Distribution[/bold]")
        curr_total = sum(curr_cats.values()) or 1
        prev_total = sum(prev_cats.values()) or 1
        all_cats = sorted(
            set(list(curr_cats.keys()) + list(prev_cats.keys())),
            key=lambda c: -curr_cats.get(c, 0),
        )
        for cat in all_cats[:6]:  # show top 6 categories
            curr_pct = curr_cats.get(cat, 0) / curr_total
            prev_pct = prev_cats.get(cat, 0) / prev_total
            delta_pct = curr_pct - prev_pct
            bar_len = int(curr_pct * 20)
            bar = "\u2588" * bar_len
            arrow = " ↑" if delta_pct > 0.03 else (" ↓" if delta_pct < -0.03 else "  ")
            console.print(f"  {cat:<12} {bar:<20} {curr_pct:.0%}{arrow}")

    return buf.getvalue()


def render_digest_history(rows: list[dict[str, Any]], period: str) -> str:
    """Render a table of past digest runs."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print(f"\n[bold]reprompt digest history ({period})[/bold]")
    console.print("=" * 40)

    if not rows:
        console.print("  No digest history found. Run `reprompt digest` to generate one.")
        return buf.getvalue()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Generated", style="dim", width=20)
    table.add_column("Window", width=27)
    table.add_column("Summary")

    for row in rows:
        generated = str(row.get("generated_at", ""))[:19]
        start = str(row.get("window_start", ""))[:10]
        end = str(row.get("window_end", ""))[:10]
        summary = str(row.get("summary", ""))
        table.add_row(generated, f"{start} → {end}", summary)

    console.print(table)
    return buf.getvalue()
