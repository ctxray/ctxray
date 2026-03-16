"""Self-contained HTML share card renderer for Wrapped reports.

Produces a complete HTML document with inline CSS (no external resources).
Uses a dark theme matching the reprompt brand.
"""

from __future__ import annotations

import html as html_mod

from reprompt.core.wrapped import WrappedReport

# Category display names and their max possible scores.
_CATEGORY_INFO: dict[str, tuple[str, float]] = {
    "structure": ("Structure", 25.0),
    "context": ("Context", 25.0),
    "position": ("Position", 20.0),
    "repetition": ("Repetition", 15.0),
    "clarity": ("Clarity", 15.0),
}


def _score_color(score: float) -> str:
    """Return a hex color based on the overall score percentage."""
    if score >= 85:
        return "#7C4DFF"
    if score >= 70:
        return "#00C853"
    if score >= 50:
        return "#FFD700"
    if score >= 30:
        return "#FF8C00"
    return "#FF4444"


def _esc(text: str) -> str:
    """Escape ``& < > " '`` for safe HTML embedding."""
    return html_mod.escape(str(text), quote=True)


def _render_category_bars(avg_scores: dict[str, float]) -> str:
    """Render score breakdown bars for each category."""
    if not avg_scores:
        return "<p>No score data available.</p>"

    rows: list[str] = []
    for key, (label, max_val) in _CATEGORY_INFO.items():
        raw = avg_scores.get(key, 0.0)
        pct = min((raw / max_val) * 100, 100) if max_val > 0 else 0
        bar_color = _score_color(pct)
        rows.append(f"""
      <div class="bar-row">
        <span class="bar-label">{_esc(label)}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width:{pct:.1f}%; background:{bar_color};"></div>
        </div>
        <span class="bar-value">{raw:.1f}</span>
      </div>""")
    return "\n".join(rows)


def _render_traits(traits: list[str]) -> str:
    """Render persona traits as an HTML list."""
    if not traits:
        return ""
    items = "\n".join(f"        <li>{_esc(t)}</li>" for t in traits)
    return f"""
      <ul class="traits">
{items}
      </ul>"""


def render_wrapped_html(report: WrappedReport) -> str:
    """Render a self-contained HTML share card.

    No external CSS/JS -- everything is inline.

    Parameters
    ----------
    report:
        A :class:`WrappedReport` containing aggregate stats and persona.

    Returns
    -------
    str
        A complete HTML document string.
    """
    score = report.avg_overall
    color = _score_color(score)
    persona = report.persona

    category_bars = _render_category_bars(report.avg_scores)
    traits_html = _render_traits(persona.traits)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>reprompt Wrapped</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0d1117;
      color: #e6edf3;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
        Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 1rem;
    }}
    .card {{
      background: #161b22;
      border-radius: 16px;
      padding: 2rem;
      max-width: 480px;
      width: 100%;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }}
    .score-section {{
      text-align: center;
      margin-bottom: 1.5rem;
    }}
    .score-number {{
      font-size: 4rem;
      font-weight: 800;
      color: {color};
      line-height: 1;
    }}
    .score-label {{
      font-size: 0.9rem;
      color: #8b949e;
      margin-top: 0.25rem;
    }}
    .persona-section {{
      text-align: center;
      margin-bottom: 1.5rem;
    }}
    .persona-emoji {{
      font-size: 2.5rem;
    }}
    .persona-name {{
      font-size: 1.4rem;
      font-weight: 700;
      text-transform: capitalize;
      margin-top: 0.25rem;
    }}
    .persona-desc {{
      font-size: 0.85rem;
      color: #8b949e;
      margin-top: 0.5rem;
      line-height: 1.4;
    }}
    .stats-row {{
      display: flex;
      justify-content: space-around;
      margin-bottom: 1.5rem;
      padding: 0.75rem 0;
      border-top: 1px solid #30363d;
      border-bottom: 1px solid #30363d;
    }}
    .stat {{
      text-align: center;
    }}
    .stat-value {{
      font-size: 1.3rem;
      font-weight: 700;
    }}
    .stat-label {{
      font-size: 0.7rem;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .breakdown-title {{
      font-size: 0.85rem;
      font-weight: 600;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.75rem;
    }}
    .bar-row {{
      display: flex;
      align-items: center;
      margin-bottom: 0.5rem;
    }}
    .bar-label {{
      width: 80px;
      font-size: 0.8rem;
      color: #c9d1d9;
    }}
    .bar-track {{
      flex: 1;
      height: 8px;
      background: #21262d;
      border-radius: 4px;
      overflow: hidden;
      margin: 0 0.5rem;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: 4px;
      transition: width 0.3s ease;
    }}
    .bar-value {{
      width: 40px;
      text-align: right;
      font-size: 0.8rem;
      color: #8b949e;
    }}
    .traits {{
      list-style: none;
      margin-top: 1rem;
      padding: 0;
    }}
    .traits li {{
      font-size: 0.8rem;
      color: #c9d1d9;
      padding: 0.25rem 0;
    }}
    .traits li::before {{
      content: "\\2022";
      color: {color};
      font-weight: 700;
      margin-right: 0.5rem;
    }}
    .footer {{
      text-align: center;
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid #30363d;
    }}
    .footer a {{
      color: #8b949e;
      font-size: 0.75rem;
      text-decoration: none;
    }}
    .footer a:hover {{
      color: #e6edf3;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="score-section">
      <div class="score-number">{score:.0f}</div>
      <div class="score-label">Overall Prompt Score</div>
    </div>

    <div class="persona-section">
      <div class="persona-emoji">{_esc(persona.emoji)}</div>
      <div class="persona-name">{_esc(persona.name)}</div>
      <div class="persona-desc">{_esc(persona.description)}</div>
    </div>

    <div class="stats-row">
      <div class="stat">
        <div class="stat-value">{report.total_prompts}</div>
        <div class="stat-label">Total Prompts</div>
      </div>
      <div class="stat">
        <div class="stat-value">{report.top_score:.0f}</div>
        <div class="stat-label">Top Score</div>
      </div>
      <div class="stat">
        <div class="stat-value">{_esc(report.top_task_type)}</div>
        <div class="stat-label">Top Task Type</div>
      </div>
    </div>

    <div class="breakdown">
      <div class="breakdown-title">Score Breakdown</div>
{category_bars}
    </div>

{traits_html}

    <div class="footer">
      <a href="https://getreprompt.dev">Generated by reprompt</a>
    </div>
  </div>
</body>
</html>"""
