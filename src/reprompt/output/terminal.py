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
    avg_compress = ov.get("avg_compressibility", 0)
    compress_line = f"\nCompressibility:   {avg_compress:.0%}" if avg_compress > 0 else ""
    overview_text = (
        f"Total prompts:     {ov['total_prompts']}\n"
        f"Unique (deduped):  {ov['unique_prompts']}\n"
        f"Sessions scanned:  {ov['sessions_scanned']}\n"
        f"Sources:           {', '.join(ov['sources']) or 'none'}\n"
        f"Date range:        {ov['date_range'][0]} → {ov['date_range'][1]}"
        f"{compress_line}"
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

    # Privacy exposure summary (compact in report)
    if data.get("privacy") and data["privacy"]["total_prompts"] > 0:
        priv = data["privacy"]
        total = priv["total_prompts"]
        cloud_pct = int(priv["cloud_prompts"] / total * 100) if total > 0 else 0
        console.print("\n[bold]Privacy Exposure[/bold]")
        console.print(
            f"  Cloud: {priv['cloud_prompts']} ({cloud_pct}%)  |  "
            f"Local: {priv['local_prompts']} ({100 - cloud_pct}%)"
        )
        if priv["training_exposed"] > 0:
            console.print(
                f"  [yellow]Training risk: {priv['training_exposed']} prompts "
                f"(opt-out/unknown policy)[/yellow]"
            )
        console.print("  Run `reprompt privacy` for full breakdown")

    console.print("\nRun `reprompt template list` to see your reusable prompt collection")
    console.print("Run `reprompt digest --trends` to see your prompt evolution over time")

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

    title = "reprompt template list"
    if category_filter:
        title += f" — {category_filter}"
    console.print(f"\n[bold]{title}[/bold]")
    console.print("=" * 40)

    if not templates:
        console.print("No templates saved yet.")
        console.print('Run [bold]reprompt template save "your prompt"[/bold] to save one.')
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
        console.print(
            "Run [bold]reprompt template save[/bold] to save ★ prompts as reusable templates."
        )

    return buf.getvalue()


def render_score(breakdown: dict[str, Any]) -> str:
    """Render a prompt score breakdown."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    total = breakdown["total"]
    grade = (
        "Excellent"
        if total >= 80
        else "Good"
        if total >= 60
        else "Fair"
        if total >= 40
        else "Poor"
        if total >= 20
        else "Very Poor"
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

    # Suggestions (sorted by impact: high → medium → low)
    suggestions = breakdown.get("suggestions", [])
    if suggestions:
        impact_order = {"high": 0, "medium": 1, "low": 2}
        suggestions = sorted(suggestions, key=lambda s: impact_order.get(s["impact"], 3))
        console.print(f"\n[bold]Suggestions ({len(suggestions)}):[/bold]")
        for s in suggestions:
            impact_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(s["impact"], "dim")
            console.print(
                f" [{impact_color}]\u25a0[/{impact_color}] [dim][{s['paper']}][/dim] {s['message']}"
            )

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

    # Per-source breakdown
    source_scores = data.get("source_scores", {})
    if source_scores:
        console.print("\n[bold]Score by Source:[/bold]")
        for src, avg in sorted(source_scores.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  {src:<20} {avg:.0f}/100")

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


def render_effectiveness_section(data: dict[str, Any]) -> str:
    """Render effectiveness section for expanded insights."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]Effectiveness[/bold]")
    console.print("\u2500" * 40)

    top = data.get("top_patterns", [])
    if top:
        console.print("  Your top patterns:")
        for p in top:
            console.print(
                f'    {p["stars"]} "{p["pattern"][:40]}" '
                f"({p['frequency']} uses, avg {p['avg_score']})"
            )

    worst = data.get("worst_pattern")
    if worst:
        console.print(
            f'  Weakest: "{worst["pattern"][:40]}" '
            f"({worst['frequency']} uses, avg {worst['avg_score']})"
        )

    return buf.getvalue()


def render_similar_prompts_section(data: dict[str, Any]) -> str:
    """Render similar prompts section for expanded insights."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]Similar Prompts[/bold]")
    console.print("\u2500" * 40)

    clusters = data.get("clusters", [])
    total = data.get("total_clusters", 0)
    console.print(f"  {total} clusters of near-duplicate prompts found")
    for c in clusters:
        console.print(f'    "{c["canonical_text"][:50]}" \u2014 {c["size"]} variations')

    return buf.getvalue()


def render_compare(data: dict[str, Any]) -> str:
    """Render a side-by-side prompt comparison."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    console.print("\n[bold]Prompt Comparison[/bold]")

    # Show prompt texts if provided (from --best-worst)
    if "prompt_a_text" in data:
        a_text = data["prompt_a_text"]
        b_text = data["prompt_b_text"]

        def _truncate(t: str) -> str:
            return (t[:77] + "...") if len(t) > 80 else t

        console.print(f"  [green]Best:[/green]  {_truncate(a_text)}")
        console.print(f"  [red]Worst:[/red] {_truncate(b_text)}")
        console.print()

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


def render_style(data: dict[str, Any]) -> str:
    """Render personal style fingerprint."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    if data["prompt_count"] == 0:
        console.print(
            "\n[dim]No prompts yet. Run 'reprompt scan' or 'reprompt import' first.[/dim]"
        )
        return buf.getvalue()

    console.print("\n[bold]Your Prompting Style[/bold]")
    console.print("\u2500" * 40)

    # One-liner summary
    pct = int(data["top_category_pct"] * 100)
    top_opener = data["opening_patterns"][0]["word"] if data["opening_patterns"] else "..."
    console.print(
        f"  {data['avg_length']:.0f}-char avg \u00b7 "
        f"{pct}% {data['top_category']} \u00b7 "
        f"opens with '{top_opener.title()}...' \u00b7 "
        f"specificity {data['specificity']:.2f}"
    )
    console.print()

    # Category breakdown
    console.print("[bold]Categories[/bold]")
    total = data["prompt_count"]
    for cat, count in sorted(data["category_distribution"].items(), key=lambda x: -x[1]):
        bar_len = int(count / total * 20)
        bar = "\u2588" * bar_len
        console.print(f"  {cat:<14} {bar} {count}")
    console.print()

    # Opening patterns
    console.print("[bold]Common Openers[/bold]")
    for p in data["opening_patterns"]:
        console.print(f"  '{p['word']}' \u2014 {p['count']}x ({int(p['pct'] * 100)}%)")
    console.print()

    # Length distribution
    console.print("[bold]Length Profile[/bold]")
    dist = data["length_distribution"]
    for bucket, label in [
        ("short", "<30"),
        ("medium", "30-80"),
        ("long", "80-200"),
        ("very_long", "200+"),
    ]:
        console.print(f"  {label:<8} {dist[bucket]}")
    console.print()

    return buf.getvalue()


def render_style_trends(data: dict[str, Any]) -> str:
    """Render style trends comparison between two periods."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    curr = data["current"]
    prev = data["previous"]
    deltas = data["deltas"]

    # Handle empty data
    if curr["prompt_count"] == 0 and prev["prompt_count"] == 0:
        console.print(
            "\n[dim]Not enough data for trends. Keep prompting and check back next week.[/dim]"
        )
        return buf.getvalue()

    if prev["prompt_count"] == 0:
        console.print(f"\n[bold]Style Trends ({data['period']})[/bold]")
        console.print("\u2500" * 40)
        console.print("  [dim]New! No previous data to compare.[/dim]")
        console.print(
            f"  Current: {curr['prompt_count']} prompts,"
            f" specificity {curr['specificity']:.2f},"
            f" avg {curr['avg_length']:.0f} chars"
        )
        return buf.getvalue()

    console.print(f"\n[bold]Style Trends ({data['period']})[/bold]")
    console.print("\u2500" * 40)

    # Specificity (green = improvement)
    spec_delta = deltas["specificity"]
    spec_sign = "+" if spec_delta > 0 else ""
    spec_pct = (
        f" ({spec_sign}{spec_delta / prev['specificity'] * 100:.0f}%)"
        if prev["specificity"] > 0
        else ""
    )
    spec_color = "green" if spec_delta > 0 else "red" if spec_delta < 0 else "dim"
    console.print(
        f"  Specificity   {prev['specificity']:.2f}"
        f" \u2192 {curr['specificity']:.2f}"
        f"  [{spec_color}]{spec_sign}{spec_delta:.2f}"
        f"{spec_pct}[/{spec_color}]"
    )

    # Avg Length (neutral, always dim)
    len_delta = deltas["avg_length"]
    len_sign = "+" if len_delta > 0 else ""
    console.print(
        f"  Avg Length    {prev['avg_length']:.0f}"
        f" \u2192 {curr['avg_length']:.0f} chars"
        f"  [dim]{len_sign}{len_delta:.0f} chars[/dim]"
    )

    # Prompt count (green = more activity)
    count_delta = deltas["prompt_count"]
    count_sign = "+" if count_delta > 0 else ""
    count_color = "green" if count_delta > 0 else "dim"
    console.print(
        f"  Prompts       {prev['prompt_count']}"
        f" \u2192 {curr['prompt_count']}"
        f"  [{count_color}]{count_sign}{count_delta}[/{count_color}]"
    )

    # Top category shift
    if deltas["top_category_changed"]:
        console.print(
            f"  Top Category  {deltas['top_category_previous']}"
            f" \u2192 {deltas['top_category_current']}"
        )
    else:
        console.print(f"  Top Category  {deltas['top_category_current']} (unchanged)")

    console.print()
    return buf.getvalue()


def render_privacy(data: dict[str, Any]) -> str:
    """Render privacy exposure summary."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    total = data["total_prompts"]
    if total == 0:
        console.print("\n[dim]No prompt data yet. Run 'reprompt scan' first.[/dim]")
        return buf.getvalue()

    cloud = data["cloud_prompts"]
    local = data["local_prompts"]
    cloud_pct = round(cloud / total * 100) if total > 0 else 0
    local_pct = round(local / total * 100) if total > 0 else 0

    console.print(f"\n[bold]Privacy Exposure[/bold] ({total} prompts)")
    console.print("\u2500" * 40)

    console.print(f"  Total prompts:   {total}")
    console.print(f"  Cloud:           {cloud} ({cloud_pct}%)")
    console.print(f"  Local:           {local} ({local_pct}%)")

    # Training exposure warning
    training_exposed = data.get("training_exposed", 0)
    if training_exposed > 0:
        console.print(
            f"\n  [yellow]\u26a0 {training_exposed} prompts may train vendor models.[/yellow]"
        )

    # Per-tool breakdown table
    sources = data.get("sources", [])
    if sources:
        console.print()
        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Tool", style="cyan", min_width=14)
        table.add_column("Prompts", justify="right")
        table.add_column("Cloud", justify="center")
        table.add_column("Retention")
        table.add_column("Training")

        for src in sources:
            cloud_icon = "\u2601\ufe0f" if src["cloud"] else "\U0001f3e0"
            training_val = src.get("training", "unknown")
            if training_val in ("opt-out", "opt-in"):
                training_display = f"[yellow]{training_val}[/yellow]"
            else:
                training_display = f"[dim]{training_val}[/dim]"

            table.add_row(
                src["name"],
                str(src["count"]),
                cloud_icon,
                src.get("retention", "unknown"),
                training_display,
            )

        console.print(table)

    console.print("\n[dim]Data policies as of March 2026. Check vendor docs for latest.[/dim]")

    return buf.getvalue()


def render_privacy_deep(scan_result: Any) -> str:
    """Render sensitive content scan results."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)

    n = scan_result.prompts_scanned
    total_findings = len(scan_result.matches)

    console.print(f"\n[bold]Sensitive Content Scan[/bold] ({n} prompts analyzed)")
    console.print("\u2500" * 45)

    if total_findings == 0:
        console.print("\n  [green]No sensitive content detected.[/green]")
        return buf.getvalue()

    # Category summary
    display_order = [
        "API keys",
        "Passwords",
        "Env secrets",
        "JWT tokens",
        "Emails",
        "IP addresses",
        "Home paths",
    ]
    for cat in display_order:
        count = scan_result.category_counts.get(cat, 0)
        if count > 0:
            sources = sorted(scan_result.category_sources.get(cat, set()))
            source_str = f" ({', '.join(sources)})" if sources else ""
            console.print(f"  {cat + ':':<16} [yellow]{count} found[/yellow]{source_str}")
        else:
            console.print(f"  {cat + ':':<16} [dim]0[/dim]")

    # Highest risk
    if scan_result.highest_risk:
        hr = scan_result.highest_risk
        console.print(
            f"\n  [bold red]Highest risk:[/bold red] "
            f"{hr.category} — {hr.matched_text} ({hr.source})"
        )

    console.print("\n[dim]Run `reprompt privacy --deep --json` for full details.[/dim]")

    return buf.getvalue()
