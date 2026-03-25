# v1.4.1 Polish Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Two UX improvements that make existing commands more useful without adding new commands.

**Version:** v1.4.1 (patch release)

---

## Feature 1: `compare --best-worst`

### Problem

`reprompt compare` requires users to manually type two prompt strings. Most users want a quick "show me my best vs worst" without digging through the database.

### Solution

Add `--best-worst` flag that auto-selects the highest-scored and lowest-scored prompts from `prompt_features`, then runs the existing comparison logic.

### Interface

```bash
# Existing (unchanged)
reprompt compare "prompt A" "prompt B"

# New
reprompt compare --best-worst
reprompt compare --best-worst --json
reprompt compare --best-worst --source claude-code
```

### Implementation Details

**CLI changes (`cli.py`):**
- `prompt_a` and `prompt_b` become `Optional[str]` (default `None`)
- Add `--best-worst` flag (bool, default `False`)
- Add `--source` filter (str, optional) for consistency
- Validation: `--best-worst` and manual prompts are mutually exclusive
- When `--best-worst`: call `db.get_best_worst_prompts(source)` to get texts, then run existing scoring logic

**DB method (`storage/db.py`):**
```python
def get_best_worst_prompts(self, source: str | None = None) -> tuple[str, str] | None:
    """Return (best_text, worst_text) from scored prompts.

    Filters to prompts with word_count >= 5 to avoid noise.
    Returns None if fewer than 2 qualifying prompts exist.
    """
```

Query: JOIN `prompt_features` ON `prompts.hash = prompt_features.prompt_hash`, filter `overall_score IS NOT NULL`, order by score DESC for best and ASC for worst. Use `features_json` to check word_count >= 5 (parsed from JSON), or do a length check on `prompts.text` (word split, len >= 5).

**Terminal output enhancement:**
When using `--best-worst`, show the prompt texts (truncated to 80 chars) above the comparison table so the user knows what's being compared.

### Edge Cases

- Fewer than 2 scored prompts: print guidance ("Run `reprompt scan` then `reprompt score` to build your score history")
- Best and worst are the same prompt (only 1 unique score): print message ("All prompts have similar scores")
- `--best-worst` combined with positional args: error with clear message

---

## Feature 2: `style --trends`

### Problem

`reprompt style` shows a static snapshot. Users have no way to see if their prompting style is improving over time.

### Solution

Add `--trends` flag that compares current period vs previous period style metrics, showing deltas.

### Interface

```bash
# Existing (unchanged)
reprompt style
reprompt style --json

# New
reprompt style --trends
reprompt style --trends --period 30d
reprompt style --trends --json
reprompt style --trends --source claude-code
```

### Implementation Details

**New function in `core/style.py`:**
```python
def compute_style_trends(
    db: PromptDB,
    period: str = "7d",
    source: str | None = None,
) -> dict[str, Any]:
    """Compare style between current and previous period.

    Returns dict with:
      period, current (style dict), previous (style dict),
      deltas: {specificity, avg_length, top_category_changed, prompt_count}
    """
```

Reuses:
- `sliding_windows(period, count=2)` from `core/timeutil`
- `db.get_prompts_in_range(start, end, source)` from existing DB
- `compute_style(prompts)` applied to each window's prompts
- `categorize_prompt()` from `core/library` to build prompt dicts

**Delta computation:**
- `specificity_delta`: current - previous (e.g., +0.12)
- `avg_length_delta`: current - previous (e.g., +15.3 chars)
- `prompt_count_delta`: current - previous
- `top_category_changed`: bool (did the top category shift?)
- `top_category_current` / `top_category_previous`: for display

**CLI changes (`cli.py`):**
- Add `--trends` flag (bool, default `False`)
- Add `--period` option (str, default `"7d"`)
- When `--trends`: call `compute_style_trends()`, render with new function

**Terminal rendering (`output/terminal.py`):**
New `render_style_trends(data)` function. Output format:

```
  Style Trends (7d)
  ─────────────────────────────────
  Specificity   0.72 → 0.84  (+12%)
  Avg Length     45 → 52 chars (+16%)
  Prompts        23 → 31  (+35%)
  Top Category   debugging → refactoring
```

Arrow notation with green for improvements, red for regressions (Rich markup). "Improvement" heuristic: higher specificity = good, but length is neutral (just show delta without color).

**JSON output:** Return raw `{period, current, previous, deltas}` dict.

### Edge Cases

- No prompts in either window: "Not enough data for trends. Keep prompting and check back next week."
- No prompts in previous window only: show current stats with "New! No previous data to compare."
- `--trends` combined with existing `--json`: works (returns trends JSON instead of snapshot JSON)

---

## What's NOT in v1.4.1

- `--copy` standardization: decided against (no clear paste destination for analysis commands)
- New commands: none
- Breaking changes: none

## Testing

- `compare --best-worst`: ~8 tests (DB method, CLI integration, edge cases, JSON output, source filter, mutual exclusion with args)
- `style --trends`: ~8 tests (compute function, CLI integration, edge cases, JSON output, source filter, period option)
- Total estimated: ~16 new tests

## Files Modified

| File | Change |
|------|--------|
| `src/reprompt/cli.py` | `compare` gains `--best-worst`/`--source`; `style` gains `--trends`/`--period` |
| `src/reprompt/storage/db.py` | Add `get_best_worst_prompts()` |
| `src/reprompt/core/style.py` | Add `compute_style_trends()` |
| `src/reprompt/output/terminal.py` | Add `render_style_trends()`, modify `render_compare()` for prompt text display |
| `pyproject.toml` | Version bump to 1.4.1 |
| `src/reprompt/__init__.py` | Version bump to 1.4.1 |
| `tests/test_compare_best_worst.py` | New test file |
| `tests/test_style_trends.py` | New test file |
