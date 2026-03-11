# HTML Dashboard Report — Design Spec

## Summary

Add `reprompt report --html` that generates a self-contained HTML dashboard combining report, trends, and recommendations into one interactive page using Chart.js.

## Command Interface

```bash
reprompt report --html              # generates report.html in cwd, opens in browser
reprompt report --html -o out.html  # custom output path
```

- `--html` flag on existing `report` command (no new subcommand)
- Default output: `./reprompt-report.html`
- Auto-opens with `webbrowser.open()` after generation
- Terminal output unchanged when `--html` is omitted

## Architecture

### New file: `src/reprompt/output/html_report.py`

Single public function:

```python
def render_html_dashboard(report_data: dict, trends_data: dict, recommend_data: dict) -> str:
    """Render all-in-one HTML dashboard. Returns complete HTML string."""
```

### Data flow

```
CLI --html flag
  → pipeline.run_full_pipeline() returns report_data
  → trends.compute_trends() returns trends_data
  → recommend.compute_recommendations() returns recommend_data
  → html_report.render_html_dashboard(report, trends, recommend)
  → write to file
  → webbrowser.open()
```

### CLI changes: `src/reprompt/cli.py`

Add `--html` flag and optional `-o`/`--output` path to the `report` command. When `--html`:
1. Collect all three data dicts (report + trends + recommendations)
2. Call `render_html_dashboard()`
3. Write to file, open in browser

## Page Layout

Single scrollable HTML page, dark theme, 7 sections:

### 1. Header + Overview Stats
- Title: "reprompt — AI Session Analytics"
- Four stat cards in a row: Total Prompts, Unique (deduped), Sessions Scanned, Date Range
- Source badges (Claude Code, OpenClaw, Cursor)

### 2. Dedup Donut Chart
- Chart.js doughnut: unique vs duplicate count
- Center label: dedup percentage
- Hover tooltip with counts

### 3. Category Distribution
- Horizontal bar chart (debug / implement / test / review / refactor)
- Color-coded by category
- Count labels on bars

### 4. Weekly Activity Trend
- Line chart from trends `windows` data
- X-axis: time window labels, Y-axis: prompt count
- Secondary Y-axis or separate line: avg prompt length

### 5. Specificity Trend
- Line chart: specificity_score over time windows
- Green/red indicators matching terminal output style
- Vocabulary size as secondary metric

### 6. Top Patterns Table
- Styled HTML table (not a chart)
- Columns: Rank, Pattern, Frequency, Category
- Top 10 patterns from report data
- Hot Phrases (TF-IDF) as a secondary table

### 7. Recommendations Section
- Best prompts table (text, score, project)
- Category effectiveness: horizontal bar chart
- Short prompt alerts: styled warning cards
- Specificity tips: before/after styled blocks

## Technical Details

### Chart.js
- Version 4.x, minified source inlined in `<script>` tag (~200KB)
- No CDN, no external dependencies
- Charts created via `new Chart(ctx, config)` in inline `<script>`

### Data injection
```html
<script>
const reportData = JSON.parse('{{ report_json }}');
const trendsData = JSON.parse('{{ trends_json }}');
const recommendData = JSON.parse('{{ recommend_json }}');
</script>
```

Data serialized with `json.dumps(data, default=str)` and escaped for HTML embedding.

### Styling
- Inline `<style>` block, no external CSS
- Dark theme (background: #1a1a2e, cards: #16213e, text: #e0e0e0)
- Responsive grid layout using CSS Grid
- Monospace font for data, sans-serif for labels

### File size
- Chart.js minified: ~200KB
- HTML template + CSS: ~15KB
- Data payload: ~5-50KB depending on prompt count
- Total: ~250-300KB

## Dependencies

**No new Python dependencies.** Only uses:
- `json` (stdlib) for data serialization
- `webbrowser` (stdlib) for auto-open
- `pathlib` (stdlib) for file paths
- String formatting for HTML template

Chart.js source stored as a string constant in `html_report.py` or loaded from a bundled file at `src/reprompt/output/chartjs.min.js`.

## What stays unchanged

- `reprompt report` (no flag) → Rich terminal output
- `reprompt trends` → Rich terminal output
- `reprompt recommend` → Rich terminal output
- All data collection, dedup, analysis pipeline unchanged
- Existing tests unaffected

## Testing

- Unit test: `render_html_dashboard()` with sample data returns valid HTML containing expected elements
- Unit test: Chart.js script tag present in output
- Unit test: data injection escaping works correctly (test with special chars in prompt text)
- Integration test: CLI `--html` flag produces a file on disk
- Manual: open generated HTML in browser, verify charts render
