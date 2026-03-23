# v1.3.1 — Actionable Suggestions + `--source` Consistency

## Goal

Two improvements: (1) guide users to the next useful command after each analysis, (2) make `--source` filtering available on all data-querying commands.

## P2: Actionable Suggestions

### Problem

Commands show data but don't tell users what to do next. New users run `reprompt scan`, see results, and don't know to try `reprompt report` or `reprompt insights`. The "展示 → 行动" gap reduces retention.

### Design

A single dim "Next step" line appended to 5 core commands:

| Command | Suggestion |
|---------|-----------|
| `scan` | `reprompt report (see results) · reprompt insights (personal patterns)` |
| `report` | `reprompt insights (patterns) · reprompt distill --last (session review)` |
| `score` | `reprompt compress "..." (optimize) · reprompt insights (all patterns)` |
| `insights` | `reprompt compress "..." (verbose prompts) · reprompt distill --last (sessions)` |
| `distill` | `reprompt compress "..." (shorten turns) · reprompt report (full analytics)` |

### Implementation

**New file:** `src/reprompt/core/suggestions.py`

```python
"""Command journey suggestions — guide users to the next useful action."""

from __future__ import annotations

SUGGESTIONS: dict[str, str] = {
    "scan": "reprompt report (see results) · reprompt insights (personal patterns)",
    "report": "reprompt insights (patterns) · reprompt distill --last (session review)",
    "score": 'reprompt compress "..." (optimize) · reprompt insights (all patterns)',
    "insights": 'reprompt compress "..." (verbose prompts) · reprompt distill --last (sessions)',
    "distill": 'reprompt compress "..." (shorten turns) · reprompt report (full analytics)',
}


def get_suggestion(command: str) -> str | None:
    """Return the suggestion line for a command, or None."""
    return SUGGESTIONS.get(command)
```

**CLI integration pattern** (same for all 5 commands):

```python
# At the end of the command function, before return:
from reprompt.core.suggestions import get_suggestion
hint = get_suggestion("command_name")
if hint and not json_output:
    console.print(f"\n  [dim]→ Try: {hint}[/dim]")
```

### Display Rules

- Only in terminal mode — suppressed when `--json` or `--copy` is used
- `[dim]` Rich styling — visible but not distracting
- Not shown when the command produces no output (e.g. `scan` with 0 new sessions, `distill` with no sessions found)
- Single line — power users can ignore it instantly

### `scan` Conflict Resolution

`scan` already has a "Try next" block (cli.py:109-114) that shows when new prompts are imported and the DB is small. The new suggestion line must NOT duplicate this. Rule: **only show the dim suggestion when the existing "Try next" block does NOT fire** — i.e. when `result.new_stored == 0` or the DB already has substantial data.

### Why Only 5 Commands

These are the commands users hit in their first session and on return visits. Adding suggestions to all 27 commands would be noise. The 5 form a natural discovery loop:

```
scan → report → insights → compress/distill → report (loop)
```

## P3: `--source` Filter Consistency

### Problem

`report`, `search`, `scan`, `lint`, `distill` support `--source` to filter by adapter. But `insights`, `trends`, `digest`, `style` don't — users with multiple tools (e.g. Claude Code + Cursor) can't analyze them separately.

### Current State

| Has `--source` | Missing (should have) | N/A (single-prompt commands) |
|---|---|---|
| `scan`, `report`, `search`, `lint`, `distill` | `insights`, `trends`, `digest`, `style` | `score`, `compare`, `compress`, `privacy` |

### Design

Add `--source` / `-s` to the 4 missing commands. Each uses existing DB query functions that already support source filtering, except `get_all_features()`.

#### DB Change: `get_all_features(source=None)`

```python
def get_all_features(self, source: str | None = None) -> list[dict[str, Any]]:
    """Return all stored feature vectors, optionally filtered by source."""
    conn = self._conn()
    try:
        if source:
            rows = conn.execute(
                """SELECT pf.features_json FROM prompt_features pf
                   JOIN prompts p ON pf.prompt_hash = p.hash
                   WHERE p.source = ?
                   ORDER BY pf.overall_score DESC""",
                (source,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT features_json FROM prompt_features ORDER BY overall_score DESC"
            ).fetchall()
        return [json.loads(r["features_json"]) for r in rows]
    finally:
        conn.close()
```

#### Per-Command Changes

| Command | Data function | Change needed |
|---------|--------------|---------------|
| `insights` | `db.get_all_features()` | Add `source` CLI param, pass to `get_all_features(source=)` |
| `style` | `db.get_all_prompts()` | Add `source` CLI param, pass to `get_all_prompts(source=)` (NOTE: `style` uses `get_all_prompts`, not `get_all_features`) |
| `trends` | `db.get_all_prompts()` | `get_all_prompts()` already accepts `source` — add CLI param and pass through |
| `digest` | `build_digest()` → `compute_window_snapshot()` → `db.get_prompts_in_range()` | Full call chain needs `source` threaded through (see below) |

#### `digest` Call Chain Fix

`digest` has a 3-function call chain that all need `source` added:

```
CLI digest(source=) → build_digest(db, period, source=) → compute_window_snapshot(db, window, period, source=) → db.get_prompts_in_range(start, end, source=)
```

**Files to modify:**
- `src/reprompt/core/digest.py`: add `source: str | None = None` param to `build_digest()`, pass to `compute_window_snapshot()`
- `src/reprompt/core/trends.py`: add `source: str | None = None` param to `compute_window_snapshot()`, pass to `db.get_prompts_in_range()`
- `db.get_prompts_in_range()` already accepts `source` — no change needed

**Digest log edge case:** When `source` is set, skip `db.log_digest()` — a source-filtered digest run should not overwrite the unfiltered digest history.

#### CLI Parameter Pattern

Standardize on `None` default (matching `distill`), not empty string:
```python
source: str | None = typer.Option(
    None, "--source", "-s", help="Filter by source (e.g. claude-code, cursor, aider)"
)
```

## Files Changed

| File | Action | What |
|------|--------|------|
| `src/reprompt/core/suggestions.py` | Create | Suggestion map + `get_suggestion()` |
| `src/reprompt/storage/db.py` | Modify | Add `source` param to `get_all_features()` |
| `src/reprompt/core/digest.py` | Modify | Add `source` param to `build_digest()` |
| `src/reprompt/core/trends.py` | Modify | Add `source` param to `compute_window_snapshot()` |
| `src/reprompt/cli.py` | Modify | Suggestions on 5 commands + `--source` on 4 commands |
| `tests/test_suggestions.py` | Create | Suggestion map tests |
| `tests/test_source_filter.py` | Create | `--source` CLI + behavioral tests (seeded DB with 2 sources) |

## DB Changes

**None.** No schema changes, no migrations. Only a query modification in `get_all_features()`.

## Testing Strategy

| Test file | Coverage |
|-----------|----------|
| `tests/test_suggestions.py` | All 5 commands return suggestions, unknown command returns None, suggestions contain valid command names |
| `tests/test_source_filter.py` | CLI `--source` flag on insights/trends/digest/style (`--help` shows flag), behavioral test with seeded DB (2 sources, verify filtered count != total count), `get_all_features(source=)` JOIN returns correct subset, digest source-filtered run skips log_digest |

## Success Criteria

1. `reprompt report` ends with a dim suggestion line pointing to `insights` and `distill`
2. `reprompt insights --source claude-code` shows patterns only from Claude Code sessions
3. `reprompt style --source cursor` shows style fingerprint from Cursor-only prompts
4. Suggestions suppressed in `--json` mode
5. Zero regressions in existing tests
