"""GitHub PR comment markdown generator.

Generates a PR comment from lint + score data using "Coach, not Judge"
psychology — celebrate good scores, encourage medium, stay minimal on low.

Design principles:
- Public PR comments should never shame. Low scores get fewer details, not red marks.
- No decorative emoji (only 🔬 ✅ ⚠️ 💡 📋).
- GitHub Alerts for instant visual status: [!TIP] green, [!NOTE] blue, [!WARNING] yellow.
- Vertical dimension table with scores (PR reviewers need numbers for decisions).
- Viral mechanic: ctxray branding appears at every score level, always neutral.

Display tiers:
- Score >= 70 (celebrate): alert + score + tier + dimensions + suggestions
- Score 50-69 (encourage): alert + score + dimensions + suggestions
- Score < 50 (minimal): alert + score + suggestions only (no dimensions)

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
    return "\u2588" * filled + "\u2591" * (width - filled)


def _tier_label(avg: float) -> str:
    """Map score to tier label. Only used for celebrate mode (>= 70)."""
    if avg >= 85:
        return "Expert"
    return "Strong"


def _alert_type(avg: float, threshold: int, passed: bool) -> str:
    """Choose GitHub Alert type based on score and threshold."""
    if avg >= 70:
        return "TIP"
    if threshold > 0 and not passed:
        return "WARNING"
    return "NOTE"


def _add_alert(lines: list[str], score: dict, total: int, model: str | None) -> None:
    """Add GitHub Alert block with summary line."""
    avg = score.get("avg_score", 0)
    threshold = score.get("threshold", 0)
    passed = score.get("pass", True)
    suggestions = score.get("top_suggestions", [])

    alert = _alert_type(avg, threshold, passed)
    lines.append(f"> [!{alert}]")

    # Build summary parts
    parts: list[str] = []

    # Score + tier
    if avg >= 70:
        tier = _tier_label(avg)
        parts.append(f"**{avg:.0f}**/100 {tier}")
    else:
        parts.append(f"**{avg:.0f}**/100")

    # Prompt count
    parts.append(f"{total} prompts")

    # Pass/fail (only when threshold set)
    if threshold > 0:
        if passed:
            parts.append(f"\u2705 Pass (\u2265{threshold})")
        else:
            parts.append(f"\u26a0\ufe0f Below target (< {threshold})")
            if suggestions:
                parts.append(f"{_pl(len(suggestions), 'suggestion')}")

    lines.append("> " + " \u00b7 ".join(parts))
    lines.append("")


def _add_dimensions(lines: list[str], score: dict) -> None:
    """Add vertical dimension table with bars and scores."""
    dims = score.get("dimensions")
    if not dims:
        return
    lines.append("| Dimension | | |")
    lines.append("|:--|:--|--:|")
    for key, name, max_val in DIMENSION_ORDER:
        avg_dim = dims.get(key, {}).get("avg", 0)
        lines.append(f"| {name} | {_bar(avg_dim, max_val)} | {avg_dim:.0f}/{max_val} |")
    lines.append("")


def _pl(n: int, word: str) -> str:
    """Pluralize: 1 suggestion, 2 suggestions."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _add_suggestions(lines: list[str], suggestions: list[dict]) -> None:
    """Add collapsible suggestions section."""
    if not suggestions:
        return
    total_points = sum(s.get("points", 0) for s in suggestions[:5])
    header = f"\U0001f4a1 {_pl(len(suggestions), 'suggestion')}"
    if total_points:
        header += f" (+{total_points} pts potential)"
    lines.append(f"<details><summary>{header}</summary>")
    lines.append("")
    for s in suggestions[:5]:
        pts = f" \u2014 **+{s['points']} pts**" if s.get("points") else ""
        paper = f" *({s['paper']})*" if s.get("paper") else ""
        count = f" ({s['count']} prompts)" if s.get("count", 0) > 1 else ""
        lines.append(f"- {s['message']}{count}{pts}{paper}")
    lines.append("")
    lines.append("</details>")
    lines.append("")


def generate_pr_comment(data: dict) -> str:
    """Generate a GitHub PR comment markdown from lint+score data.

    All score tiers show the numeric score (PR reviewers need numbers for
    merge decisions). Coach psychology is expressed through tone and
    progressive disclosure, not information hiding.

    Args:
        data: Dict with keys: total_prompts, errors, warnings, violations,
              and optionally score (with dimensions, tiers, top_suggestions),
              model (target model name).

    Returns:
        Markdown string ready to post as a PR comment.
    """
    lines: list[str] = [COMMENT_MARKER]

    total = data.get("total_prompts", 0)
    score = data.get("score")
    violations = data.get("violations", [])
    model = data.get("model")

    # -- Header --
    header = "\U0001f52c ctxray \u00b7 Prompt Quality Report"
    if model:
        header += f" `{model}`"
    lines.append(f"### {header}")
    lines.append("")

    if score:
        avg = score.get("avg_score", 0)
        suggestions = score.get("top_suggestions", [])

        # -- GitHub Alert with summary --
        _add_alert(lines, score, total, model)

        if avg >= 70:
            # CELEBRATE: dimensions + suggestions
            _add_dimensions(lines, score)
            _add_suggestions(lines, suggestions)

        elif avg >= 50:
            # ENCOURAGE: dimensions + suggestions
            _add_dimensions(lines, score)
            _add_suggestions(lines, suggestions)

        else:
            # MINIMAL: suggestions only (dimensions all low, not informative)
            _add_suggestions(lines, suggestions)

    else:
        # -- No scoring: lint-only mode --
        if not violations:
            lines.append(f"**{total}** prompts analyzed \u00b7 all clear \u2705")
        else:
            lines.append(f"**{total}** prompts analyzed")
        lines.append("")

    # -- Lint items (collapsible, neutral language) --
    if violations:
        lines.append(
            f"<details><summary>\U0001f4cb {_pl(len(violations), 'item')} to review</summary>"
        )
        lines.append("")
        lines.append("| | Rule | Message |")
        lines.append("|-|------|---------|")
        for v in violations[:20]:
            sev = "\u26a0\ufe0f" if v.get("severity") == "error" else "\U0001f4a1"
            lines.append(f"| {sev} | `{v.get('rule', '')}` | {v.get('message', '')} |")
        if len(violations) > 20:
            lines.append(f"| | | *\u2026 and {len(violations) - 20} more* |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # -- Branded footer --
    lines.append("---")
    lines.append(
        f'<sub><a href="{FOOTER_URL}">ctxray</a>'
        f" \u2014 prompt quality linter \u00b7 rule-based \u00b7 <50ms \u00b7 no LLM"
        f" \u00b7 <code>pip install ctxray</code></sub>"
    )

    return "\n".join(lines) + "\n"
