"""HTML dashboard report renderer.

Produces a self-contained HTML page with Chart.js visualizations,
stat cards, tables, and recommendations.
"""

from __future__ import annotations

import html as html_mod
import json
from pathlib import Path
from typing import Any


def _load_chartjs() -> str:
    """Load Chart.js source from the bundled minified file."""
    chartjs_path = Path(__file__).parent / "chartjs.min.js"
    return chartjs_path.read_text(encoding="utf-8")


def _safe_json(data: Any) -> str:
    """Serialize data to JSON safe for embedding inside <script> tags.

    Replaces ``</`` with ``<\\/`` to prevent premature script closing.
    """
    raw = json.dumps(data, ensure_ascii=False, default=str)
    return raw.replace("</", r"<\/")


def _html_escape(text: str) -> str:
    """Escape ``& < > " '`` for safe HTML embedding."""
    return html_mod.escape(text, quote=True)


def render_html_dashboard(
    report_data: dict[str, Any],
    trends_data: dict[str, Any],
    recommend_data: dict[str, Any],
    digest_data: dict[str, Any] | None = None,
) -> str:
    """Render a complete self-contained HTML dashboard page.

    Parameters
    ----------
    report_data:
        Core report with overview, patterns, categories, terms, clusters.
    trends_data:
        Prompt evolution trends with windows and insights.
    recommend_data:
        Recommendations with best prompts, alerts, tips.
    digest_data:
        Optional weekly digest comparing current vs previous period.

    Returns
    -------
    str
        Complete HTML document string.
    """
    chartjs_src = _load_chartjs()

    overview = report_data.get("overview", {})
    total = overview.get("total_prompts", 0)
    unique = overview.get("unique_prompts", 0)
    sessions = overview.get("sessions_scanned", 0)
    sources = overview.get("sources", [])
    date_range = overview.get("date_range", ("", ""))

    # Build patterns table rows
    patterns_rows = ""
    for p in report_data.get("top_patterns", []):
        txt = _html_escape(str(p.get("pattern_text", "")))
        freq = p.get("frequency", 0)
        cat = _html_escape(str(p.get("category", "")))
        patterns_rows += (
            f'<tr><td>{txt}</td><td>{freq}</td><td><span class="badge">{cat}</span></td></tr>\n'
        )

    # Build hot-terms table rows
    terms_rows = ""
    for t in report_data.get("top_terms", []):
        term = _html_escape(str(t.get("term", "")))
        avg = t.get("tfidf_avg", 0)
        df = t.get("df", 0)
        terms_rows += f"<tr><td>{term}</td><td>{avg:.3f}</td><td>{df}</td></tr>\n"

    # Build best-prompts table rows
    best_rows = ""
    for bp in recommend_data.get("best_prompts", []):
        txt = _html_escape(str(bp.get("text", "")))
        eff = bp.get("effectiveness", 0)
        proj = _html_escape(str(bp.get("project", "")))
        best_rows += f"<tr><td>{txt}</td><td>{eff:.0%}</td><td>{proj}</td></tr>\n"

    # Build short-prompt alerts
    alerts_html = ""
    for a in recommend_data.get("short_prompt_alerts", []):
        txt = _html_escape(str(a.get("text", "")))
        cnt = a.get("char_count", 0)
        alerts_html += (
            f'<div class="alert-item"><strong>"{txt}"</strong> &mdash; only {cnt} chars</div>\n'
        )

    # Build specificity tips
    spec_tips_html = ""
    for s in recommend_data.get("specificity_tips", []):
        orig = _html_escape(str(s.get("original", "")))
        tip = _html_escape(str(s.get("tip", "")))
        spec_tips_html += f'<div class="tip-item"><em>"{orig}"</em> &rarr; {tip}</div>\n'

    # Build general tips
    tips_html = ""
    for tip in recommend_data.get("category_tips", []):
        tips_html += f"<li>{_html_escape(str(tip))}</li>\n"
    for tip in recommend_data.get("overall_tips", []):
        tips_html += f"<li>{_html_escape(str(tip))}</li>\n"

    # Build insights
    insights_html = ""
    for ins in trends_data.get("insights", []):
        insights_html += f"<li>{_html_escape(str(ins))}</li>\n"

    # Build digest comparison block
    digest_html = ""
    if digest_data:
        count_delta = digest_data.get("count_delta", 0)
        spec_delta = digest_data.get("spec_delta", 0.0)
        eff_avg = digest_data.get("eff_avg")
        curr = digest_data.get("current", {})
        period = _html_escape(str(digest_data.get("period", "7d")))

        def _delta_cls(v: float, threshold: float = 0.01) -> str:
            if v > threshold:
                return "delta-up"
            if v < -threshold:
                return "delta-down"
            return "delta-neutral"

        def _sign(v: float) -> str:
            return "+" if v > 0 else ""

        count_cls = _delta_cls(float(count_delta))
        spec_cls = _delta_cls(spec_delta)
        count_sign = _sign(float(count_delta))
        spec_sign = _sign(spec_delta)
        spec_curr = curr.get("specificity_score", 0.0)

        eff_card = ""
        if eff_avg is not None:
            eff_card = (
                f'<div class="stat-card">'
                f'<div class="value">{eff_avg:.2f}</div>'
                f'<div class="label">Avg Quality</div>'
                f"</div>"
            )

        # Category delta mini-table
        curr_cats = curr.get("category_distribution", {})
        prev_cats = digest_data.get("previous", {}).get("category_distribution", {})
        cat_rows = ""
        if curr_cats:
            curr_total = sum(curr_cats.values()) or 1
            prev_total = sum(prev_cats.values()) or 1
            top_cats = sorted(curr_cats, key=lambda c: -curr_cats[c])[:6]
            for cat in top_cats:
                cp = curr_cats.get(cat, 0) / curr_total
                pp = prev_cats.get(cat, 0) / prev_total
                dp = cp - pp
                arrow = "↑" if dp > 0.03 else ("↓" if dp < -0.03 else "→")
                cls = "delta-up" if dp > 0.03 else ("delta-down" if dp < -0.03 else "delta-neutral")
                cat_rows += (
                    f"<tr><td>{_html_escape(cat)}</td>"
                    f"<td>{cp:.0%}</td>"
                    f'<td class="{cls}">{arrow} {dp:+.0%}</td></tr>\n'
                )
        cat_section = ""
        if cat_rows:
            cat_section = (
                "<h3 style='margin:16px 0 8px'>Category Shift</h3>"
                "<table><thead><tr>"
                "<th>Category</th><th>This Period</th><th>Change</th>"
                "</tr></thead>"
                f"<tbody>{cat_rows}</tbody></table>"
            )

        digest_html = f"""
<div class="section">
  <div class="card">
    <h2>This {period} vs Previous</h2>
    <div class="stats-row" style="margin-bottom:0">
      <div class="stat-card">
        <div class="value {count_cls}">{count_sign}{count_delta}</div>
        <div class="label">Prompt Count Change</div>
      </div>
      <div class="stat-card">
        <div class="value {spec_cls}">{spec_sign}{spec_delta:+.2f}</div>
        <div class="label">Specificity Change</div>
      </div>
      <div class="stat-card">
        <div class="value">{spec_curr:.2f}</div>
        <div class="label">Current Specificity</div>
      </div>
      {eff_card}
    </div>
    {cat_section}
  </div>
</div>
"""

    # Build clusters table
    clusters_rows = ""
    for cl in report_data.get("clusters", []):
        cid = cl.get("cluster_id", "")
        size = cl.get("size", 0)
        sample = _html_escape(str(cl.get("sample", "")))
        clusters_rows += f"<tr><td>#{cid}</td><td>{size}</td><td>{sample}</td></tr>\n"
    _no_cluster_msg = "<p>Not enough data for clustering (need 5+ prompts).</p>"
    _cluster_inner = (
        f"<table><thead><tr><th>#</th><th>Size</th><th>Sample</th></tr></thead>"
        f"<tbody>{clusters_rows}</tbody></table>"
    )
    clusters_table = _cluster_inner if clusters_rows else _no_cluster_msg

    # Date range footer
    dr_start = _html_escape(str(date_range[0])) if date_range[0] else "N/A"
    dr_end = _html_escape(str(date_range[1])) if date_range[1] else "N/A"

    report_json = _safe_json(report_data)
    trends_json = _safe_json(trends_data)
    recommend_json = _safe_json(recommend_data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>reprompt — Prompt Analytics</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #1a1a2e; color: #e0e0e0; padding: 24px;
  line-height: 1.6;
}}
h1 {{ text-align: center; margin-bottom: 8px; font-size: 2rem; letter-spacing: -0.5px; }}
h1 .re {{ color: #888; font-weight: 400; }}
h1 .prompt {{ color: #e94560; font-weight: 700; }}
.subtitle {{
  text-align: center; color: #666; margin-bottom: 32px;
  font-size: 0.82rem; letter-spacing: 0.08em; text-transform: uppercase;
}}
.stats-row {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px; margin-bottom: 32px;
}}
.stat-card {{
  background: #16213e; border-radius: 12px; padding: 20px; text-align: center;
}}
.stat-card .value {{ font-size: 2rem; font-weight: 700; color: #e94560; }}
.stat-card .label {{ font-size: 0.85rem; color: #aaa; margin-top: 4px; }}
.chart-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px; margin-bottom: 32px;
}}
.card {{
  background: #16213e; border-radius: 12px; padding: 24px;
}}
.card h2 {{ font-size: 1.1rem; margin-bottom: 16px; color: #e94560; }}
canvas {{ width: 100% !important; max-height: 320px; }}
table {{
  width: 100%; border-collapse: collapse; font-size: 0.9rem;
}}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #2a2a4a; }}
th {{ color: #e94560; font-weight: 600; }}
.badge {{
  background: #e94560; color: #fff; padding: 2px 10px; border-radius: 12px;
  font-size: 0.78rem;
}}
.section {{ margin-bottom: 32px; }}
.section h2 {{ color: #e94560; margin-bottom: 16px; font-size: 1.2rem; }}
.alert-item {{
  background: #2a1a1a; border-left: 3px solid #e94560; padding: 10px 14px;
  margin-bottom: 8px; border-radius: 4px;
}}
.tip-item {{
  background: #1a2a1a; border-left: 3px solid #4caf50; padding: 10px 14px;
  margin-bottom: 8px; border-radius: 4px;
}}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 6px; }}
.footer {{
  text-align: center; color: #666; font-size: 0.8rem; margin-top: 40px;
  padding-top: 16px; border-top: 1px solid #2a2a4a;
}}
.delta-up {{ color: #4caf50; }}
.delta-down {{ color: #e94560; }}
.delta-neutral {{ color: #aaa; }}
@media (max-width: 860px) {{
  .chart-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<h1><span class="re">re</span><span class="prompt">prompt</span></h1>
<p class="subtitle">Prompt Analytics</p>

<!-- Stat cards -->
<div class="stats-row">
  <div class="stat-card">
    <div class="value">{total}</div>
    <div class="label">Total Prompts</div>
  </div>
  <div class="stat-card">
    <div class="value">{unique}</div>
    <div class="label">Unique Prompts</div>
  </div>
  <div class="stat-card">
    <div class="value">{sessions}</div>
    <div class="label">Sessions Scanned</div>
  </div>
  <div class="stat-card">
    <div class="value">{len(sources)}</div>
    <div class="label">Sources</div>
  </div>
</div>

{digest_html}
<!-- Charts 2x2 -->
<div class="chart-grid">
  <div class="card">
    <h2>Deduplication</h2>
    <canvas id="dedupChart"></canvas>
  </div>
  <div class="card">
    <h2>Category Distribution</h2>
    <canvas id="categoryChart"></canvas>
  </div>
  <div class="card">
    <h2>Activity Over Time</h2>
    <canvas id="activityChart"></canvas>
  </div>
  <div class="card">
    <h2>Specificity Trend</h2>
    <canvas id="specificityChart"></canvas>
  </div>
</div>

<!-- Tables -->
<div class="section">
  <div class="card">
    <h2>Top Patterns</h2>
    <table>
      <thead><tr><th>Pattern</th><th>Freq</th><th>Category</th></tr></thead>
      <tbody>{patterns_rows}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="card">
    <h2>Hot Phrases (TF-IDF)</h2>
    <table>
      <thead><tr><th>Term</th><th>Avg TF-IDF</th><th>Doc Freq</th></tr></thead>
      <tbody>{terms_rows}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="card">
    <h2>Prompt Clusters</h2>
    {clusters_table}
  </div>
</div>

<!-- Recommendations -->
<div class="section">
  <div class="card">
    <h2>Best Prompts</h2>
    <table>
      <thead><tr><th>Prompt</th><th>Effectiveness</th><th>Project</th></tr></thead>
      <tbody>{best_rows}</tbody>
    </table>
  </div>
</div>

<div class="chart-grid">
  <div class="card">
    <h2>Category Effectiveness</h2>
    <canvas id="effectivenessChart"></canvas>
  </div>
</div>

<div class="section">
  <div class="card">
    <h2>Short Prompt Alerts</h2>
    {alerts_html if alerts_html else "<p>No alerts.</p>"}
  </div>
</div>

<div class="section">
  <div class="card">
    <h2>Specificity Tips</h2>
    {spec_tips_html if spec_tips_html else "<p>No tips.</p>"}
  </div>
</div>

<div class="section">
  <div class="card">
    <h2>Tips</h2>
    <ul>{tips_html if tips_html else "<li>No tips available.</li>"}</ul>
  </div>
</div>

<div class="section">
  <div class="card">
    <h2>Insights</h2>
    <ul>{insights_html if insights_html else "<li>No insights available.</li>"}</ul>
  </div>
</div>

<div class="footer">
  Date range: {dr_start} &mdash; {dr_end} | Generated by reprompt
</div>

<!-- Chart.js -->
<script>{chartjs_src}</script>

<!-- Data injection -->
<script>
const reportData = {report_json};
const trendsData = {trends_json};
const recommendData = {recommend_json};
</script>

<!-- Charts -->
<script>
(function() {{
  const COLORS = [
    '#e94560', '#0f3460', '#533483', '#4caf50',
    '#ff9800', '#2196f3', '#9c27b0', '#00bcd4'
  ];

  // Dedup donut
  const dedupCtx = document.getElementById('dedupChart');
  if (dedupCtx) {{
    const ov = reportData.overview || {{}};
    const dupes = (ov.total_prompts || 0) - (ov.unique_prompts || 0);
    new Chart(dedupCtx, {{
      type: 'doughnut',
      data: {{
        labels: ['Unique', 'Duplicates'],
        datasets: [{{
          data: [ov.unique_prompts || 0, dupes],
          backgroundColor: ['#4caf50', '#e94560']
        }}]
      }},
      options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }} }}
    }});
  }}

  // Category bar
  const catCtx = document.getElementById('categoryChart');
  if (catCtx) {{
    const cats = reportData.categories || {{}};
    const labels = Object.keys(cats);
    const values = Object.values(cats);
    new Chart(catCtx, {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [{{
          label: 'Count', data: values,
          backgroundColor: COLORS.slice(0, labels.length)
        }}]
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{ ticks: {{ color: '#e0e0e0' }} }},
          y: {{ ticks: {{ color: '#e0e0e0' }}, beginAtZero: true }}
        }},
        plugins: {{ legend: {{ display: false }} }}
      }}
    }});
  }}

  // Activity line
  const actCtx = document.getElementById('activityChart');
  if (actCtx) {{
    const wins = (trendsData.windows || []);
    const labels = wins.map(w => w.window_label || '');
    const counts = wins.map(w => w.prompt_count || 0);
    new Chart(actCtx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [{{
          label: 'Prompts', data: counts,
          borderColor: '#e94560', backgroundColor: 'rgba(233,69,96,0.15)',
          fill: true, tension: 0.3
        }}]
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{ ticks: {{ color: '#e0e0e0' }} }},
          y: {{ ticks: {{ color: '#e0e0e0' }}, beginAtZero: true }}
        }},
        plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }}
      }}
    }});
  }}

  // Specificity line
  const specCtx = document.getElementById('specificityChart');
  if (specCtx) {{
    const wins = (trendsData.windows || []);
    const labels = wins.map(w => w.window_label || '');
    const scores = wins.map(w => w.specificity_score || 0);
    new Chart(specCtx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [{{
          label: 'Specificity', data: scores,
          borderColor: '#4caf50', backgroundColor: 'rgba(76,175,80,0.15)',
          fill: true, tension: 0.3
        }}]
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{ ticks: {{ color: '#e0e0e0' }} }},
          y: {{ ticks: {{ color: '#e0e0e0' }}, beginAtZero: true }}
        }},
        plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }}
      }}
    }});
  }}

  // Category effectiveness bar
  const effCtx = document.getElementById('effectivenessChart');
  if (effCtx) {{
    const eff = recommendData.category_effectiveness || {{}};
    const labels = Object.keys(eff);
    const values = Object.values(eff);
    new Chart(effCtx, {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [{{
          label: 'Effectiveness', data: values,
          backgroundColor: COLORS.slice(0, labels.length)
        }}]
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{ ticks: {{ color: '#e0e0e0' }} }},
          y: {{ ticks: {{ color: '#e0e0e0' }}, beginAtZero: true, max: 1.0 }}
        }},
        plugins: {{ legend: {{ display: false }} }}
      }}
    }});
  }}
}})();
</script>

</body>
</html>"""
