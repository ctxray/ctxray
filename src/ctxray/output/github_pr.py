"""GitHub PR comment markdown generator.

Generates a visually striking PR comment from lint + score data.
Designed as a viral distribution surface — every PR comment is a brand impression.

Usage in action.yml:
    ctxray lint --format github --score-threshold 50 > /tmp/comment.md
"""

from __future__ import annotations

COMMENT_MARKER = "<!-- ctxray-lint -->"
FOOTER_URL = "https://github.com/ctxray/ctxray"

# Tier thresholds (must match scorer.get_tier)
TIER_THRESHOLDS = [
    ("Expert", 85),
    ("Strong", 70),
    ("Good", 50),
    ("Basic", 30),
    ("Draft", 0),
]

DIMENSION_ORDER = [
    ("clarity", "Clarity", 25),
    ("context", "Context", 25),
    ("position", "Position", 20),
    ("structure", "Structure", 15),
    ("repetition", "Repetition", 15),
]


def _tier_emoji(score: float) -> str:
    if score >= 85:
        return "🟣"
    if score >= 70:
        return "🟢"
    if score >= 50:
        return "🟡"
    if score >= 30:
        return "🟠"
    return "🔴"


def _tier_label(score: float) -> str:
    for label, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return label
    return "Draft"


def _status_line(errors: int, warnings: int, score_pass: bool | None) -> tuple[str, str]:
    """Return (status_text, status_emoji)."""
    if errors > 0:
        return "Failed", "❌"
    if score_pass is False:
        return "Below threshold", "❌"
    if warnings > 0:
        return "Passed with warnings", "⚠️"
    return "Passed", "✅"


def _bar(value: float, max_val: int, width: int = 10) -> str:
    """Unicode progress bar for markdown."""
    filled = round(value / max_val * width) if max_val > 0 else 0
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def generate_pr_comment(data: dict) -> str:
    """Generate a GitHub PR comment markdown from lint+score data.

    Args:
        data: Dict with keys: total_prompts, errors, warnings, violations,
              and optionally score (with dimensions, tiers, top_suggestions).

    Returns:
        Markdown string ready to post as a PR comment.
    """
    lines: list[str] = [COMMENT_MARKER]

    total = data.get("total_prompts", 0)
    errors = data.get("errors", 0)
    warnings = data.get("warnings", 0)
    score = data.get("score")
    violations = data.get("violations", [])

    # ── Header line ──
    if score:
        avg = score.get("avg_score", 0)
        tier = _tier_label(avg)
        threshold = score.get("threshold", 0)
        score_pass = score.get("pass")
        _, status_emoji = _status_line(errors, warnings, score_pass)
        lines.append(f"### 🔬 ctxray · {avg:.0f}/100 {tier} · {status_emoji}")
    else:
        _, status_emoji = _status_line(errors, warnings, None)
        status_text, _ = _status_line(errors, warnings, None)
        lines.append(f"### 🔬 ctxray lint · {status_emoji} {status_text}")

    lines.append("")

    # ── Dimension breakdown (when scoring is enabled) ──
    if score and score.get("dimensions"):
        dims = score["dimensions"]
        # Header row
        names = [name for _, name, _ in DIMENSION_ORDER]
        lines.append("| " + " | ".join(names) + " |")
        lines.append("|" + "|".join(":---:" for _ in DIMENSION_ORDER) + "|")
        # Values row with mini bars
        cells = []
        for key, _, max_val in DIMENSION_ORDER:
            avg_dim = dims.get(key, {}).get("avg", 0)
            bar = _bar(avg_dim, max_val)
            cells.append(f"{avg_dim:.0f}/{max_val} {bar}")
        lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    # ── Summary line ──
    parts = [f"**{total}** prompts analyzed"]
    if errors:
        parts.append(f"**{errors}** errors")
    if warnings:
        parts.append(f"**{warnings}** warnings")
    if score and score.get("threshold", 0) > 0:
        threshold = score["threshold"]
        avg = score.get("avg_score", 0)
        passed = "passed" if score.get("pass") else "failed"
        parts.append(f"threshold {threshold} — {passed}")
    lines.append(" · ".join(parts))
    lines.append("")

    # ── Tier distribution (when available) ──
    if score and score.get("tiers"):
        tiers = score["tiers"]
        total_scored = sum(tiers.values())
        if total_scored > 0:
            lines.append("<details><summary>📊 Score distribution</summary>")
            lines.append("")
            lines.append("| Tier | Prompts | |")
            lines.append("|------|--------:|-|")
            for label, threshold in TIER_THRESHOLDS:
                count = tiers.get(label, 0)
                if count > 0 or label in ("Expert", "Draft"):
                    bar = "█" * max(1, round(count / total_scored * 20)) if count > 0 else ""
                    lines.append(f"| {label} ({threshold}+) | {count} | {bar} |")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    # ── Top suggestions (when available) ──
    if score and score.get("top_suggestions"):
        suggestions = score["top_suggestions"][:5]
        total_points = sum(s.get("points", 0) for s in suggestions)
        lines.append(
            f"<details><summary>💡 Top improvements"
            f"{f' (+{total_points} pts possible)' if total_points else ''}"
            f"</summary>"
        )
        lines.append("")
        for s in suggestions:
            pts = f" — **+{s['points']} pts**" if s.get("points") else ""
            paper = f" *({s['paper']})*" if s.get("paper") else ""
            count = f" ({s['count']} prompts)" if s.get("count", 0) > 1 else ""
            lines.append(f"- {s['message']}{count}{pts}{paper}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # ── Violations (collapsible) ──
    if violations:
        lines.append(f"<details><summary>📋 {len(violations)} violation(s)</summary>")
        lines.append("")
        lines.append("| | Rule | Message |")
        lines.append("|-|------|---------|")
        for v in violations[:20]:
            sev = "🔴" if v.get("severity") == "error" else "🟡"
            lines.append(f"| {sev} | `{v.get('rule', '')}` | {v.get('message', '')} |")
        if len(violations) > 20:
            lines.append(f"| | | *… and {len(violations) - 20} more* |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # ── Branded footer ──
    lines.append("---")
    lines.append(
        f'<sub>Analyzed by <a href="{FOOTER_URL}">ctxray</a>'
        f" · X-ray your AI coding sessions · <code>pip install ctxray</code></sub>"
    )

    return "\n".join(lines) + "\n"
