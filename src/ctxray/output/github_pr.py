"""GitHub PR comment markdown generator.

Generates a PR comment from lint + score data using "Coach, not Judge"
psychology — celebrate good scores, encourage medium, stay minimal on low.

Design principles:
- Public PR comments should never shame. Low scores → fewer details, not red marks.
- ❌ never appears for quality scores. Only ⚠️ for CI gate failures the user chose.
- "Violation" → "item to review". "Failed" → "below target". Coach language.
- Viral mechanic: ctxray branding appears at every score level, always neutral or positive.

Display tiers:
- Score ≥ 70 (celebrate): show score + tier + dimensions + suggestions
- Score 50-69 (encourage): show dimensions + suggestions, no total score
- Score < 50 (minimal): show only suggestion count, no score, no dimensions

Usage in action.yml:
    ctxray lint --format github --score-threshold 50 > /tmp/comment.md
"""

from __future__ import annotations

COMMENT_MARKER = "<!-- ctxray-lint -->"
FOOTER_URL = "https://github.com/ctxray/ctxray"

DIMENSION_ORDER = [
    ("clarity", "Clarity", 25),
    ("context", "Context", 25),
    ("position", "Position", 20),
    ("structure", "Structure", 15),
    ("repetition", "Repetition", 15),
]


def _bar(value: float, max_val: int, width: int = 10) -> str:
    """Unicode progress bar for markdown."""
    filled = round(value / max_val * width) if max_val > 0 else 0
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def _add_dimensions(lines: list[str], score: dict) -> None:
    """Add the 5-dimension score table."""
    dims = score.get("dimensions")
    if not dims:
        return
    names = [name for _, name, _ in DIMENSION_ORDER]
    lines.append("| " + " | ".join(names) + " |")
    lines.append("|" + "|".join(":---:" for _ in DIMENSION_ORDER) + "|")
    cells = []
    for key, _, max_val in DIMENSION_ORDER:
        avg_dim = dims.get(key, {}).get("avg", 0)
        bar = _bar(avg_dim, max_val)
        cells.append(f"{avg_dim:.0f}/{max_val} {bar}")
    lines.append("| " + " | ".join(cells) + " |")
    lines.append("")


def _add_suggestions(lines: list[str], suggestions: list[dict], label: str) -> None:
    """Add collapsible suggestions section."""
    if not suggestions:
        return
    total_points = sum(s.get("points", 0) for s in suggestions[:5])
    header = f"💡 {label}"
    if total_points:
        header += f" (+{total_points} pts potential)"
    lines.append(f"<details><summary>{header}</summary>")
    lines.append("")
    for s in suggestions[:5]:
        pts = f" — **+{s['points']} pts**" if s.get("points") else ""
        paper = f" *({s['paper']})*" if s.get("paper") else ""
        count = f" ({s['count']} prompts)" if s.get("count", 0) > 1 else ""
        lines.append(f"- {s['message']}{count}{pts}{paper}")
    lines.append("")
    lines.append("</details>")
    lines.append("")


def generate_pr_comment(data: dict) -> str:
    """Generate a GitHub PR comment markdown from lint+score data.

    Uses conditional display depth based on score:
    - ≥70: celebrate (full score + dimensions)
    - 50-69: encourage (dimensions only, no total)
    - <50: minimal (suggestions only)

    Args:
        data: Dict with keys: total_prompts, errors, warnings, violations,
              and optionally score (with dimensions, tiers, top_suggestions).

    Returns:
        Markdown string ready to post as a PR comment.
    """
    lines: list[str] = [COMMENT_MARKER]

    total = data.get("total_prompts", 0)
    score = data.get("score")
    violations = data.get("violations", [])

    # ── Header (always neutral) ──
    lines.append("### 🔬 ctxray · Prompt Quality Report")
    lines.append("")

    if score:
        avg = score.get("avg_score", 0)
        threshold = score.get("threshold", 0)
        suggestions = score.get("top_suggestions", [])

        if avg >= 70:
            # ── CELEBRATE: score + tier + dimensions ──
            tier = "Expert" if avg >= 85 else "Strong"
            lines.append(f"**{avg:.0f}**/100 {tier} — your prompts are well-structured ✨")
            lines.append("")
            _add_dimensions(lines, score)
            parts = [f"**{total}** prompts analyzed"]
            if suggestions:
                parts.append(f"💡 {len(suggestions)} suggestions to push even higher")
            lines.append(" · ".join(parts))
            lines.append("")
            _add_suggestions(lines, suggestions, "View suggestions")

        elif avg >= 50:
            # ── ENCOURAGE: dimensions + suggestions, no total score ──
            _add_dimensions(lines, score)
            parts = [f"**{total}** prompts analyzed"]
            if suggestions:
                n = len(suggestions)
                total_pts = sum(s.get("points", 0) for s in suggestions[:5])
                hint = f"💡 {n} quick wins available"
                if total_pts:
                    hint += f" (+{total_pts} pts potential)"
                parts.append(hint)
            lines.append(" · ".join(parts))
            lines.append("")
            _add_suggestions(lines, suggestions, "View suggestions")

        else:
            # ── MINIMAL: just count + suggestions, no score, no dimensions ──
            parts = [f"**{total}** prompts analyzed"]
            if suggestions:
                parts.append(f"💡 {len(suggestions)} suggestions available")
            lines.append(" · ".join(parts))
            lines.append("")
            _add_suggestions(lines, suggestions, "View suggestions")

        # ── CI gate (only when user set a threshold) ──
        if threshold > 0:
            if score.get("pass"):
                lines.append(f"✅ Meets project target ({avg:.0f} ≥ {threshold})")
            else:
                lines.append(f"⚠️ Below project target ({avg:.0f} < {threshold})")
            lines.append("")

    else:
        # ── No scoring: lint-only mode ──
        if not violations:
            lines.append(f"**{total}** prompts analyzed · all clear ✅")
        else:
            lines.append(f"**{total}** prompts analyzed")
        lines.append("")

    # ── Lint items (collapsible, neutral language) ──
    if violations:
        lines.append(f"<details><summary>📋 {len(violations)} items to review</summary>")
        lines.append("")
        lines.append("| | Rule | Message |")
        lines.append("|-|------|---------|")
        for v in violations[:20]:
            sev = "⚠️" if v.get("severity") == "error" else "💡"
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
