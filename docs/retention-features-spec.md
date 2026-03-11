# Retention Features Specification

Created: 2026-03-11
Author: architect-agent
Status: Draft

## Overview

reprompt currently operates as a batch tool: scan, dedup, analyze, report. Users run it once,
get a snapshot, and have no reason to return. This spec defines five features that create daily
engagement loops by surfacing time-based insights, quality signals, contextual suggestions,
curation tools, and periodic summaries.

All features share a single SQLite database, require zero external services, and follow the
existing patterns in `src/reprompt/` (Typer CLI, Rich output, pydantic-settings, sklearn).

---

## Shared Infrastructure

Before diving into individual features, several pieces of infrastructure are needed across
multiple features. Building these first avoids duplication and establishes the foundation.

### Time-Series Query Layer

Features 1, 2, and 5 all need to query prompts by time window. Today the `prompts` table
has a `timestamp TEXT` column but no indexed time queries. A shared utility module solves this
once.

**New file: `src/reprompt/core/timeutil.py`**

```python
"""Time-window query utilities shared across retention features."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class TimeWindow:
    """A half-open time interval [start, end)."""
    start: datetime
    end: datetime
    label: str  # e.g. "2026-W10", "2026-03", "last-7d"


def parse_period(period: str) -> timedelta:
    """Parse '7d', '4w', '1m', '1y' into a timedelta."""
    m = re.fullmatch(r"(\d+)([dwmy])", period.strip().lower())
    if not m:
        raise ValueError(f"Invalid period: {period}. Use 7d, 4w, 1m, etc.")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return timedelta(days=n)
    if unit == "w":
        return timedelta(weeks=n)
    if unit == "m":
        return timedelta(days=n * 30)  # approximate
    if unit == "y":
        return timedelta(days=n * 365)
    raise ValueError(f"Unknown unit: {unit}")


def sliding_windows(
    period: str = "7d",
    count: int = 4,
    anchor: datetime | None = None,
) -> list[TimeWindow]:
    """Generate `count` consecutive windows of `period` length ending at `anchor`.

    Returns windows in chronological order (oldest first).
    """
    if anchor is None:
        anchor = datetime.now(timezone.utc)
    delta = parse_period(period)
    windows = []
    for i in range(count - 1, -1, -1):
        end = anchor - delta * i
        start = end - delta
        windows.append(TimeWindow(start=start, end=end, label=f"period-{count - i}"))
    return windows
```

### Session Metadata Extraction

Features 2 and 5 need richer data from session files than the current adapter extracts.
Rather than modifying the adapter ABC (breaking change), a new `SessionMeta` model and an
enrichment pass during scan capture this data.

**New file: `src/reprompt/core/session_meta.py`**

```python
"""Session-level metadata extraction for effectiveness scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionMeta:
    """Metadata about an AI coding session."""
    session_id: str
    source: str
    project: str
    start_time: str
    end_time: str
    duration_seconds: int
    prompt_count: int
    tool_call_count: int
    error_count: int          # assistant messages containing error/traceback
    final_status: str         # "success" | "error" | "unknown"
    avg_prompt_length: float
```

### Snapshot Table

Features 1 and 5 need point-in-time aggregate metrics stored so that period comparisons
do not require recomputing from raw prompts every time.

**New table: `prompt_snapshots`** (details in schema section below)

---

## Feature 1: Prompt Evolution Tracking

### User Story

> As a developer who uses AI coding tools daily, I want to see how my prompting skills
> improve over time so that I can identify growth areas and maintain good habits.

### CLI Interface

```
reprompt trends [OPTIONS]

Options:
  --period TEXT     Time bucket size: 7d (default), 14d, 30d, 1m
  --windows INT    Number of periods to compare (default: 4)
  --format TEXT    Output format: terminal (default), json
```

**Examples:**
```bash
reprompt trends                    # last 4 weeks, week-by-week
reprompt trends --period 30d       # last 4 months, month-by-month
reprompt trends --windows 8        # last 8 periods
reprompt trends --format json      # pipe to jq or dashboard
```

### Metrics Computed Per Window

| Metric | Derivation | Insight |
|--------|-----------|---------|
| `prompt_count` | COUNT of prompts in window | Volume |
| `unique_count` | COUNT WHERE duplicate_of IS NULL | How many are original |
| `avg_length` | AVG(char_count) | Specificity proxy |
| `median_length` | Median of char_count | Robust specificity |
| `vocab_size` | Count of distinct whitespace-split tokens | Vocabulary breadth |
| `category_distribution` | {category: count} using `categorize_prompt()` | Skill shifts |
| `top_terms_shift` | TF-IDF top-10 delta vs previous window | Topic evolution |
| `specificity_score` | Composite: length + vocab + category diversity | Single number |

#### Specificity Score Formula

```
specificity = 0.4 * norm(avg_length, 50, 500)
            + 0.3 * norm(vocab_size, 20, 200)
            + 0.3 * category_entropy / max_entropy
```

Where `norm(x, lo, hi)` clamps and scales to [0, 1], and `category_entropy` is Shannon
entropy of the category distribution (more diverse = higher).

### Terminal Output

```
reprompt trends — Prompt Evolution

Period          Prompts  Avg Len  Vocab  Specificity
Feb 17 - Feb 23     42     127     89     0.52
Feb 24 - Mar 02     38     156    104     0.64  ↑ +23%
Mar 03 - Mar 09     45     171    118     0.71  ↑ +11%
Mar 10 - Mar 16     51     183    132     0.78  ↑ +10%

Trend: Your prompts are getting more specific (+50% in 4 weeks)

Category Shifts:
  implement  ████████████  38% → 42%  ↑
  debug      ██████        18% → 12%  ↓  (fewer bugs!)
  explain    ████          12% → 15%  ↑
  review     ███           10% → 14%  ↑
```

### Data Model Changes

```sql
CREATE TABLE IF NOT EXISTS prompt_snapshots (
    id INTEGER PRIMARY KEY,
    window_start TEXT NOT NULL,       -- ISO-8601
    window_end TEXT NOT NULL,         -- ISO-8601
    window_label TEXT,                -- "2026-W10", "2026-03", etc.
    period TEXT NOT NULL,             -- "7d", "30d", etc.
    prompt_count INTEGER NOT NULL,
    unique_count INTEGER NOT NULL,
    avg_length REAL,
    median_length REAL,
    vocab_size INTEGER,
    specificity_score REAL,
    category_distribution TEXT,       -- JSON: {"debug": 5, "implement": 12, ...}
    top_terms TEXT,                   -- JSON: [{"term": "...", "tfidf": 0.12}, ...]
    computed_at TEXT NOT NULL         -- ISO-8601, when snapshot was taken
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_window
    ON prompt_snapshots (window_start, period);
```

### Implementation Plan

**New files:**
- `src/reprompt/core/timeutil.py` — shared time utilities (see above)
- `src/reprompt/core/trends.py` — snapshot computation and comparison logic
- `tests/test_trends.py` — unit tests for trends computation

**Modified files:**
- `src/reprompt/cli.py` — add `trends` command
- `src/reprompt/storage/db.py` — add `prompt_snapshots` table, query methods
- `src/reprompt/output/terminal.py` — add `render_trends()` function
- `src/reprompt/output/json_out.py` — add `format_trends_json()`

**Core logic (`trends.py`):**

```python
def compute_window_snapshot(
    db: PromptDB,
    window: TimeWindow,
    period: str,
) -> dict[str, Any]:
    """Query prompts in a time window and compute aggregate metrics."""
    ...

def compute_trends(
    db: PromptDB,
    period: str = "7d",
    windows: int = 4,
) -> list[dict[str, Any]]:
    """Compute snapshots for N consecutive windows and annotate deltas."""
    ...

def generate_insights(snapshots: list[dict]) -> list[str]:
    """Produce natural-language insights from trend data."""
    ...
```

**New DB methods:**
```python
def get_prompts_in_range(self, start: str, end: str) -> list[dict[str, Any]]:
    """Return prompts with timestamp >= start AND < end."""
    ...

def upsert_snapshot(self, snapshot: dict[str, Any]) -> None:
    """Insert or update a prompt_snapshot row."""
    ...

def get_snapshots(self, period: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return recent snapshots for a given period."""
    ...
```

### Minimum Viable Version

MVP is the `trends` command with:
- `prompt_count`, `avg_length`, `vocab_size` per window (no specificity composite yet)
- Delta arrows (up/down) between consecutive windows
- Terminal table only (no JSON)
- No snapshot caching (recompute on each run)

Add specificity score, category shifts, insights, JSON output, and snapshot persistence in v2.

### Estimated Complexity: **Medium**

---

## Feature 2: Prompt Effectiveness Score

### User Story

> As a developer, I want to know which of my prompt patterns actually lead to productive
> sessions so that I can reuse effective patterns and retire ineffective ones.

### Effectiveness Heuristic

Since we cannot instrument the AI tool's output quality directly, we derive effectiveness
from session metadata observable in the JSONL files:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Session completed without trailing errors | 0.30 | Last 3 messages have no error/traceback = clean exit |
| Reasonable duration (10min - 2h) | 0.15 | Too short = abandoned, too long = struggling |
| Tool calls > 0 | 0.10 | AI actually did work, not just chat |
| Low error-to-tool ratio | 0.25 | Few errors per tool call = smooth session |
| Prompt specificity (length + vocab) | 0.20 | Specific prompts correlate with better outcomes |

```python
def compute_effectiveness(meta: SessionMeta, prompt_specificity: float) -> float:
    """Return effectiveness score in [0.0, 1.0]."""
    score = 0.0

    # Clean exit
    if meta.final_status == "success":
        score += 0.30
    elif meta.final_status == "unknown":
        score += 0.15  # partial credit

    # Duration
    if 600 <= meta.duration_seconds <= 7200:
        score += 0.15
    elif meta.duration_seconds > 7200:
        score += 0.05

    # Tool calls exist
    if meta.tool_call_count > 0:
        score += 0.10

    # Error ratio
    if meta.tool_call_count > 0:
        error_ratio = meta.error_count / meta.tool_call_count
        score += 0.25 * max(0, 1 - error_ratio * 2)

    # Specificity
    score += 0.20 * prompt_specificity

    return round(min(score, 1.0), 2)
```

### Session Final-Status Detection

Parsing the last N lines of a session JSONL to determine `final_status`:

```python
def detect_final_status(session_lines: list[dict]) -> str:
    """Check last 3 assistant messages for error indicators."""
    ERROR_PATTERNS = [
        "error", "Error", "ERROR",
        "traceback", "Traceback",
        "failed", "Failed", "FAILED",
        "exception", "Exception",
    ]
    last_assistant = [
        m for m in session_lines[-10:]
        if m.get("role") == "assistant" or m.get("type") == "assistant"
    ][-3:]

    for msg in last_assistant:
        text = str(msg.get("content", msg.get("message", {}).get("content", "")))
        if any(p in text for p in ERROR_PATTERNS):
            return "error"
    return "success"
```

### CLI Interface

The effectiveness score appears in two places:

1. **Enrichment of existing commands:**
```bash
reprompt library
# Pattern                  Uses  Category  Effectiveness
# "Fix the failing test"    12   debug     0.72 ★★★☆☆
# "Add endpoint for..."      8   implement 0.91 ★★★★★
```

2. **Dedicated command:**
```bash
reprompt effectiveness [OPTIONS]

Options:
  --period TEXT    Time window to analyze (default: 30d)
  --top INT        Top N patterns by effectiveness (default: 10)
  --worst INT      Bottom N patterns (default: 0)
  --format TEXT    terminal (default), json
```

**Terminal output:**
```
reprompt effectiveness — Pattern Effectiveness (last 30 days)

Top Patterns by Outcome:
#  Pattern                          Uses  Score  Rating
1  "Implement the X endpoint..."     8    0.91   ★★★★★
2  "Add unit tests for..."           6    0.85   ★★★★☆
3  "Refactor X to use Y pattern"     4    0.82   ★★★★☆

Patterns to Improve:
#  Pattern                          Uses  Score  Rating
1  "Fix the bug"                    11    0.38   ★★☆☆☆
2  "Why is this broken"              5    0.29   ★☆☆☆☆

Insight: Specific prompts (avg 180 chars) score 2.4x higher than vague ones (avg 35 chars)
```

### Data Model Changes

```sql
CREATE TABLE IF NOT EXISTS session_meta (
    session_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    project TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_seconds INTEGER,
    prompt_count INTEGER,
    tool_call_count INTEGER,
    error_count INTEGER,
    final_status TEXT,            -- "success" | "error" | "unknown"
    avg_prompt_length REAL,
    scanned_at TEXT NOT NULL      -- ISO-8601
);

-- Effectiveness per prompt linked to its session
ALTER TABLE prompts ADD COLUMN effectiveness_score REAL;

-- Effectiveness per pattern (aggregate of member prompts)
ALTER TABLE prompt_patterns ADD COLUMN effectiveness_avg REAL;
ALTER TABLE prompt_patterns ADD COLUMN effectiveness_sample_size INTEGER DEFAULT 0;
```

### Implementation Plan

**New files:**
- `src/reprompt/core/session_meta.py` — `SessionMeta` dataclass (see shared infrastructure)
- `src/reprompt/core/effectiveness.py` — score computation, final-status detection
- `tests/test_effectiveness.py` — unit tests

**Modified files:**
- `src/reprompt/adapters/claude_code.py` — add `parse_session_meta()` method
- `src/reprompt/adapters/openclaw.py` — add `parse_session_meta()` method
- `src/reprompt/adapters/base.py` — add `parse_session_meta()` to ABC (with default impl)
- `src/reprompt/core/pipeline.py` — call `parse_session_meta()` during scan, store results
- `src/reprompt/storage/db.py` — add `session_meta` table, methods for querying/aggregating
- `src/reprompt/cli.py` — add `effectiveness` command
- `src/reprompt/output/terminal.py` — add `render_effectiveness()`, modify `render_library()`

**Adapter extension (non-breaking):**

```python
# In base.py
class BaseAdapter(ABC):
    ...
    def parse_session_meta(self, path: Path) -> SessionMeta | None:
        """Parse session-level metadata. Returns None if not enough data."""
        return None  # default: adapters that don't support it
```

```python
# In claude_code.py
class ClaudeCodeAdapter(BaseAdapter):
    ...
    def parse_session_meta(self, path: Path) -> SessionMeta | None:
        """Extract session metadata from JSONL by reading all entries."""
        entries = []
        with open(path) as f:
            for line in f:
                ...  # parse all entries, not just user messages
        # Compute: timestamps, tool_call_count, error_count, final_status
        ...
```

### Minimum Viable Version

MVP:
- `session_meta` table populated during scan
- `effectiveness_score` computed per session, averaged to pattern level
- `reprompt library` shows score column
- No dedicated `reprompt effectiveness` command yet (add in v2)

### Estimated Complexity: **Large**

---

## Feature 3: Smart Prompt Suggestions (MCP Server)

### User Story

> As a developer using Claude Code or Cursor, I want relevant past prompts suggested to me
> based on what I am currently working on, so I can reuse my best patterns without leaving
> my editor.

### MCP Server Architecture

```
reprompt MCP Server (stdio transport)
├── Tools
│   ├── search_similar_prompts(query, limit?) -> list[Prompt]
│   ├── get_best_prompts(category?, min_score?) -> list[Pattern]
│   └── log_prompt_feedback(prompt_hash, useful: bool)
└── Resources
    ├── reprompt://library                -> full pattern library (JSON)
    ├── reprompt://library/{category}     -> patterns filtered by category
    ├── reprompt://trends/latest          -> latest trends snapshot (JSON)
    └── reprompt://stats                  -> database statistics
```

### MCP Protocol Details

The server uses **stdio transport** (the standard for local MCP servers). It is launched by
the client (Claude Code, Cursor) as a subprocess.

**Client configuration (Claude Code `~/.claude/claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "reprompt": {
      "command": "reprompt",
      "args": ["mcp-serve"],
      "env": {}
    }
  }
}
```

### Tool Definitions

#### `search_similar_prompts`

```json
{
  "name": "search_similar_prompts",
  "description": "Search your prompt history for prompts similar to the given context or query. Returns past prompts that match, ranked by relevance.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The current task context or search terms"
      },
      "limit": {
        "type": "integer",
        "description": "Max results to return (default 5)",
        "default": 5
      },
      "category": {
        "type": "string",
        "description": "Optional category filter (debug, implement, test, etc.)"
      }
    },
    "required": ["query"]
  }
}
```

**Implementation:** Use TF-IDF cosine similarity against stored prompts (same engine as
dedup, but used for retrieval). If Feature 2 is implemented, results include effectiveness
scores.

#### `get_best_prompts`

```json
{
  "name": "get_best_prompts",
  "description": "Get your highest-rated prompt patterns by category. Patterns with proven effectiveness are ranked higher.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "Category to filter (debug, implement, review, test, refactor, explain, config)"
      },
      "min_effectiveness": {
        "type": "number",
        "description": "Minimum effectiveness score (0.0-1.0, default 0.5)",
        "default": 0.5
      },
      "limit": {
        "type": "integer",
        "default": 5
      }
    }
  }
}
```

#### `log_prompt_feedback`

```json
{
  "name": "log_prompt_feedback",
  "description": "Record whether a suggested prompt was helpful.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "prompt_hash": { "type": "string" },
      "useful": { "type": "boolean" }
    },
    "required": ["prompt_hash", "useful"]
  }
}
```

### Data Model Changes

```sql
-- Feedback from MCP tool usage
CREATE TABLE IF NOT EXISTS prompt_feedback (
    id INTEGER PRIMARY KEY,
    prompt_hash TEXT NOT NULL,
    useful INTEGER NOT NULL,       -- 1 = useful, 0 = not useful
    context TEXT,                   -- what the user was doing when feedback given
    recorded_at TEXT NOT NULL       -- ISO-8601
);

CREATE INDEX IF NOT EXISTS idx_feedback_hash ON prompt_feedback (prompt_hash);
```

### CLI Interface

```bash
reprompt mcp-serve           # start MCP server (stdio, launched by client)
reprompt mcp-install         # write config to claude_desktop_config.json
```

### Implementation Plan

**New dependency:**
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0"]
```

The `mcp` package provides the Python SDK for building MCP servers.

**New files:**
- `src/reprompt/mcp/__init__.py`
- `src/reprompt/mcp/server.py` — MCP server implementation
- `src/reprompt/mcp/tools.py` — tool handler functions
- `src/reprompt/mcp/resources.py` — resource provider functions
- `tests/test_mcp_server.py` — unit tests (mock stdio transport)

**Modified files:**
- `src/reprompt/cli.py` — add `mcp-serve` and `mcp-install` commands
- `src/reprompt/storage/db.py` — add `prompt_feedback` table, feedback methods
- `pyproject.toml` — add `mcp` optional dependency

**Server skeleton (`mcp/server.py`):**

```python
"""MCP server exposing reprompt library as tools and resources."""

from mcp.server import Server
from mcp.server.stdio import stdio_server

from reprompt.config import Settings
from reprompt.storage.db import PromptDB

app = Server("reprompt")

@app.list_tools()
async def list_tools():
    ...

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    ...

@app.list_resources()
async def list_resources():
    ...

@app.read_resource()
async def read_resource(uri: str):
    ...

async def main():
    settings = Settings()
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
```

### Minimum Viable Version

MVP:
- `search_similar_prompts` tool only (no effectiveness integration)
- `reprompt://library` resource only
- `reprompt mcp-serve` command
- `reprompt mcp-install` for Claude Code config
- No feedback logging yet

### Estimated Complexity: **Medium**

---

## Feature 4: Prompt Merge & Consolidation

### User Story

> As a developer with hundreds of similar prompts, I want to merge near-duplicates into
> refined "golden" versions that I can reuse, so my library stays clean and actionable.

### CLI Interface

```bash
reprompt consolidate [OPTIONS]

Options:
  --threshold FLOAT   Similarity threshold for grouping (default: 0.6)
  --min-group INT     Minimum cluster size to show (default: 3)
  --auto              Auto-merge without prompting (picks longest as golden)
  --dry-run           Show what would be merged without making changes
  --category TEXT     Only consolidate within a category
```

**Interactive flow:**

```
reprompt consolidate

Found 4 groups of similar prompts:

Group 1 (5 prompts, similarity: 0.72):
  1. "Fix the failing test in auth module"
  2. "Fix the test that's failing in auth"
  3. "Fix failing auth test"
  4. "Fix the auth module test failure"
  5. "Fix the broken test in auth"

  Actions:
  [m] Merge → pick golden version
  [e] Edit → write custom golden version
  [s] Skip this group
  [q] Quit

  Choice: m
  Select golden version (1-5, or 0 to write custom): 1

  ✓ Merged 5 prompts → "Fix the failing test in auth module"
    Stored as curated pattern with 5 examples

Group 2 (3 prompts, similarity: 0.68):
  ...

Summary: Consolidated 12 prompts into 3 curated patterns
```

### Data Model Changes

```sql
-- Curated "golden" prompts created by consolidation
CREATE TABLE IF NOT EXISTS curated_prompts (
    id INTEGER PRIMARY KEY,
    golden_text TEXT NOT NULL,         -- the refined prompt text
    golden_hash TEXT UNIQUE,           -- SHA-256 of golden_text
    category TEXT,
    source_count INTEGER,              -- how many raw prompts were merged
    source_hashes TEXT,                -- JSON array of original prompt hashes
    user_notes TEXT,                   -- optional user annotation
    effectiveness_avg REAL,            -- inherited from source prompts if available
    created_at TEXT NOT NULL,          -- ISO-8601
    updated_at TEXT NOT NULL           -- ISO-8601
);

CREATE INDEX IF NOT EXISTS idx_curated_category ON curated_prompts (category);

-- Link table: which raw prompts were consolidated into which curated prompt
CREATE TABLE IF NOT EXISTS consolidation_links (
    curated_id INTEGER REFERENCES curated_prompts(id),
    prompt_id INTEGER REFERENCES prompts(id),
    PRIMARY KEY (curated_id, prompt_id)
);
```

### Consolidation Algorithm

```python
def find_consolidation_groups(
    db: PromptDB,
    threshold: float = 0.6,
    min_group: int = 3,
    category: str | None = None,
) -> list[ConsolidationGroup]:
    """Find groups of similar prompts suitable for merging.

    1. Fetch all non-duplicate prompts (optionally filtered by category)
    2. Compute TF-IDF matrix
    3. Greedy clustering at `threshold` (same algorithm as library.extract_patterns)
    4. Filter groups with >= min_group members
    5. For each group, rank members by length (longer = more specific = better golden candidate)
    """
    ...
```

```python
@dataclass
class ConsolidationGroup:
    prompts: list[dict[str, Any]]     # raw prompts in the group
    similarity: float                  # average pairwise similarity
    suggested_golden: str              # longest prompt text as default
    category: str
```

### Auto-Merge Logic

When `--auto` is used:
1. Pick the longest prompt in each group as the golden version
2. Create `curated_prompts` entry
3. Create `consolidation_links` entries
4. Print summary

### Integration Points

- `reprompt library` should show curated prompts with a marker (e.g., `[curated]`)
- MCP server `get_best_prompts` should prefer curated prompts
- `reprompt trends` could track curated-to-raw ratio as a library health metric

### Implementation Plan

**New files:**
- `src/reprompt/core/consolidation.py` — grouping algorithm, merge logic
- `tests/test_consolidation.py` — unit tests

**Modified files:**
- `src/reprompt/cli.py` — add `consolidate` command
- `src/reprompt/storage/db.py` — add tables, query/insert methods for curated prompts
- `src/reprompt/output/terminal.py` — add interactive consolidation renderer

**New DB methods:**
```python
def insert_curated_prompt(self, golden_text: str, source_hashes: list[str],
                          category: str, user_notes: str = "") -> int: ...
def get_curated_prompts(self, category: str | None = None) -> list[dict]: ...
def link_consolidation(self, curated_id: int, prompt_ids: list[int]) -> None: ...
```

### Minimum Viable Version

MVP:
- `reprompt consolidate --auto --dry-run` (show groups, no interactive)
- `reprompt consolidate --auto` (auto-merge, pick longest)
- No interactive mode yet (add in v2)
- No user notes yet
- No integration with library/MCP yet

### Estimated Complexity: **Medium**

---

## Feature 5: Weekly Digest

### User Story

> As a developer, I want a quick summary of my AI prompting activity each week, showing
> what changed, what worked, and what to focus on, without having to remember to run
> multiple commands.

### CLI Interface

```bash
reprompt digest [OPTIONS]

Options:
  --period TEXT    Comparison window: 7d (default), 14d, 30d
  --format TEXT    terminal (default), json, markdown
  --quiet          One-line summary only (for hook/cron use)
```

**Terminal output:**
```
reprompt digest — Weekly Summary (Mar 4 - Mar 10 vs Feb 25 - Mar 3)

Activity:
  Prompts this week:    51  (+34% vs last week)
  Sessions:              8  (+2)
  New patterns found:    3

Quality:
  Avg prompt length:   183 chars  (+15%)
  Specificity score:  0.78  (↑ from 0.71)
  Top effectiveness:   "Add unit tests for..." (0.91)

Category Shifts:
  implement  ████████████  42%  (was 38%)
  debug      ██████        12%  (was 18%)  ↓ Good — fewer debugging prompts!
  test       ████          15%  (was 10%)  ↑ More testing!

New Patterns Discovered:
  1. "Refactor X to use dependency injection"  (4 uses)
  2. "Add integration test for X endpoint"     (3 uses)
  3. "Review X for security vulnerabilities"   (3 uses)

Most Used Pattern:
  "Implement the X feature with Y approach" (12 uses, effectiveness: 0.85)

💡 Tip: Your debug prompts are 2x more effective when you include the error message.
        Try: "Fix [error]: [message] in [file]" instead of "fix the bug"
```

**Quiet mode (for hooks/cron):**
```
reprompt: 51 prompts (+34%), specificity 0.78 (↑), 3 new patterns
```

### Auto-Trigger via Hook

The existing `install-hook` command can be extended to optionally show the digest
when a new session starts (post-scan).

```bash
# In the installed hook script:
reprompt scan --source claude-code 2>/dev/null
reprompt digest --quiet 2>/dev/null || true
```

### Digest Data Assembly

The digest is a composition of data from other features:

```python
def build_digest(
    db: PromptDB,
    period: str = "7d",
) -> DigestData:
    """Assemble digest by querying across features."""
    now = datetime.now(timezone.utc)
    current_window = TimeWindow(now - parse_period(period), now, "current")
    previous_window = TimeWindow(
        now - parse_period(period) * 2,
        now - parse_period(period),
        "previous",
    )

    current = compute_window_snapshot(db, current_window, period)  # from Feature 1
    previous = compute_window_snapshot(db, previous_window, period)

    # New patterns: patterns with first_seen in current window
    new_patterns = db.get_patterns_since(current_window.start.isoformat())

    # Most used pattern in current window
    most_used = db.get_most_used_pattern_in_range(
        current_window.start.isoformat(),
        current_window.end.isoformat(),
    )

    # Tip generation
    tip = generate_tip(current, previous)

    return DigestData(
        current=current,
        previous=previous,
        new_patterns=new_patterns,
        most_used=most_used,
        tip=tip,
    )
```

### Data Model Changes

```sql
-- Track when digests were generated (avoid showing stale data)
CREATE TABLE IF NOT EXISTS digest_log (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,              -- "7d", "30d"
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    generated_at TEXT NOT NULL,        -- ISO-8601
    summary TEXT                       -- one-line summary for quiet mode cache
);
```

### Tip Generation

Tips are generated from comparing current vs previous window data:

```python
TIP_RULES = [
    # (condition_fn, tip_template)
    (
        lambda c, p: c["avg_length"] < 50 and p["avg_length"] < 50,
        "Your prompts average only {avg_length} chars. Try adding context: "
        "what file, what error, what you've already tried."
    ),
    (
        lambda c, p: c["categories"].get("debug", 0) > c["prompt_count"] * 0.3,
        "Over 30% of your prompts are debugging. Consider adding more tests "
        "upfront — your 'test' prompts have {test_eff:.0%} effectiveness."
    ),
    (
        lambda c, p: c["specificity_score"] > p.get("specificity_score", 0) + 0.1,
        "Great progress! Your specificity score improved by "
        "{delta:.0%} this period. Keep it up."
    ),
]
```

### Implementation Plan

**New files:**
- `src/reprompt/core/digest.py` — digest assembly, tip generation
- `tests/test_digest.py` — unit tests

**Modified files:**
- `src/reprompt/cli.py` — add `digest` command
- `src/reprompt/storage/db.py` — add `digest_log` table, new query methods
- `src/reprompt/output/terminal.py` — add `render_digest()`
- `src/reprompt/output/markdown.py` — add `export_digest_markdown()`
- `src/reprompt/output/json_out.py` — add `format_digest_json()`

**Dependencies on other features:**
- Depends on Feature 1 (trends) for `compute_window_snapshot()`
- Optionally uses Feature 2 (effectiveness) for quality insights
- Works without Features 2-4 (gracefully degrades)

### Minimum Viable Version

MVP:
- Activity section only (prompt count, sessions, delta arrows)
- Category distribution comparison
- No tips, no effectiveness integration, no new patterns section
- Terminal output only
- `--quiet` mode for hook usage

### Estimated Complexity: **Small** (if Feature 1 is built first)

---

## Priority Order and Dependencies

```
Feature 1: Trends       ─────────────────────────────── Foundation
    │                                                      │
    ├── Feature 5: Digest  (depends on Feature 1)          │ Phase 1
    │                                                      │
Feature 2: Effectiveness ──────────── Enrichment           │ Phase 2
    │                                                      │
    ├── Feature 3: MCP Server (enhanced by Feature 2)      │ Phase 3
    │                                                      │
Feature 4: Consolidation ──────────── Curation             │ Phase 3
```

### Recommended Build Order

| Phase | Feature | Complexity | Dependencies | Daily Value |
|-------|---------|-----------|--------------|-------------|
| 1a | Shared time utils + DB queries | S | None | Enables all |
| 1b | Feature 1: Trends | M | 1a | High — first "come back" reason |
| 1c | Feature 5: Digest | S | 1b | High — daily engagement hook |
| 2 | Feature 2: Effectiveness | L | 1a | Medium — enriches everything |
| 3a | Feature 3: MCP Server | M | None (enhanced by 2) | High — real-time value |
| 3b | Feature 4: Consolidation | M | None (enhanced by 2) | Medium — library hygiene |

### Shared Infrastructure Usage

| Infrastructure | Used by Features |
|---------------|-----------------|
| `timeutil.py` (time windows) | 1, 2, 5 |
| `prompt_snapshots` table | 1, 5 |
| `session_meta` table | 2, 5 |
| `get_prompts_in_range()` | 1, 2, 4, 5 |
| TF-IDF similarity search | 3, 4 |
| `categorize_prompt()` | 1, 2, 5 (already exists) |

---

## Complete Schema Migration

All new tables in a single migration, applied via `_init_schema()` in `db.py`:

```sql
-- Retention features: prompt_snapshots
CREATE TABLE IF NOT EXISTS prompt_snapshots (
    id INTEGER PRIMARY KEY,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    window_label TEXT,
    period TEXT NOT NULL,
    prompt_count INTEGER NOT NULL,
    unique_count INTEGER NOT NULL,
    avg_length REAL,
    median_length REAL,
    vocab_size INTEGER,
    specificity_score REAL,
    category_distribution TEXT,
    top_terms TEXT,
    computed_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_window
    ON prompt_snapshots (window_start, period);

-- Retention features: session_meta
CREATE TABLE IF NOT EXISTS session_meta (
    session_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    project TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_seconds INTEGER,
    prompt_count INTEGER,
    tool_call_count INTEGER,
    error_count INTEGER,
    final_status TEXT,
    avg_prompt_length REAL,
    scanned_at TEXT NOT NULL
);

-- Retention features: prompt_feedback (MCP)
CREATE TABLE IF NOT EXISTS prompt_feedback (
    id INTEGER PRIMARY KEY,
    prompt_hash TEXT NOT NULL,
    useful INTEGER NOT NULL,
    context TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_hash ON prompt_feedback (prompt_hash);

-- Retention features: curated_prompts (consolidation)
CREATE TABLE IF NOT EXISTS curated_prompts (
    id INTEGER PRIMARY KEY,
    golden_text TEXT NOT NULL,
    golden_hash TEXT UNIQUE,
    category TEXT,
    source_count INTEGER,
    source_hashes TEXT,
    user_notes TEXT,
    effectiveness_avg REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_curated_category ON curated_prompts (category);

-- Retention features: consolidation_links
CREATE TABLE IF NOT EXISTS consolidation_links (
    curated_id INTEGER REFERENCES curated_prompts(id),
    prompt_id INTEGER REFERENCES prompts(id),
    PRIMARY KEY (curated_id, prompt_id)
);

-- Retention features: digest_log
CREATE TABLE IF NOT EXISTS digest_log (
    id INTEGER PRIMARY KEY,
    period TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    summary TEXT
);

-- Column additions to existing tables (use separate ALTER statements for SQLite compat)
-- These are idempotent: check column existence before ALTER
-- prompts.effectiveness_score REAL
-- prompt_patterns.effectiveness_avg REAL
-- prompt_patterns.effectiveness_sample_size INTEGER DEFAULT 0
```

**SQLite column addition strategy:** Since SQLite does not support `ADD COLUMN IF NOT EXISTS`,
wrap each `ALTER TABLE` in a try/except block:

```python
def _migrate_add_column(conn, table, column, col_type, default=None):
    """Add a column if it doesn't exist. SQLite-safe."""
    try:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}")
    except sqlite3.OperationalError:
        pass  # column already exists
```

---

## New File Summary

| File | Feature | Purpose |
|------|---------|---------|
| `src/reprompt/core/timeutil.py` | Shared | Time window parsing and generation |
| `src/reprompt/core/session_meta.py` | Shared | SessionMeta dataclass |
| `src/reprompt/core/trends.py` | 1 | Snapshot computation, comparison, insights |
| `src/reprompt/core/effectiveness.py` | 2 | Score computation, final-status detection |
| `src/reprompt/core/digest.py` | 5 | Digest assembly, tip generation |
| `src/reprompt/core/consolidation.py` | 4 | Grouping, merge logic |
| `src/reprompt/mcp/__init__.py` | 3 | MCP package init |
| `src/reprompt/mcp/server.py` | 3 | MCP server entry point |
| `src/reprompt/mcp/tools.py` | 3 | Tool handler implementations |
| `src/reprompt/mcp/resources.py` | 3 | Resource provider implementations |
| `tests/test_timeutil.py` | Shared | Time utility tests |
| `tests/test_trends.py` | 1 | Trends computation tests |
| `tests/test_effectiveness.py` | 2 | Effectiveness scoring tests |
| `tests/test_digest.py` | 5 | Digest assembly tests |
| `tests/test_consolidation.py` | 4 | Consolidation algorithm tests |
| `tests/test_mcp_server.py` | 3 | MCP server tests |

## Modified File Summary

| File | Features | Changes |
|------|----------|---------|
| `src/reprompt/cli.py` | 1,2,3,4,5 | Add 5 new commands: trends, effectiveness, mcp-serve, mcp-install, consolidate, digest |
| `src/reprompt/storage/db.py` | All | New tables, new query methods, column migrations |
| `src/reprompt/core/pipeline.py` | 2 | Session meta extraction during scan |
| `src/reprompt/adapters/base.py` | 2 | Add `parse_session_meta()` to ABC |
| `src/reprompt/adapters/claude_code.py` | 2 | Implement `parse_session_meta()` |
| `src/reprompt/adapters/openclaw.py` | 2 | Implement `parse_session_meta()` |
| `src/reprompt/output/terminal.py` | 1,2,4,5 | Render functions for new commands |
| `src/reprompt/output/json_out.py` | 1,2,5 | JSON formatters for new commands |
| `src/reprompt/output/markdown.py` | 5 | Digest markdown export |
| `src/reprompt/config.py` | 1,5 | New settings: default_period, digest_auto_show |
| `pyproject.toml` | 3 | Add `mcp` optional dependency |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Effectiveness heuristic is inaccurate | Users lose trust in scores | Label as "experimental", allow user override via feedback table, expose heuristic weights in config |
| Session JSONL format changes | Adapter breaks, no meta extracted | Graceful fallback: `parse_session_meta()` returns None, features degrade to "no data" |
| MCP SDK breaking changes | Server stops working | Pin `mcp` version, use optional dependency so core CLI unaffected |
| Large prompt databases slow down TF-IDF | Consolidation/search takes seconds | Add `LIMIT` to queries, cache TF-IDF matrices, index timestamp column |
| Interactive consolidation UX is complex | Users abandon the feature | Provide `--auto` mode first, interactive is v2 |
| Timestamp column has empty/missing values | Time queries return incomplete data | Filter `WHERE timestamp != ''` (already done in purge), document requirement |

---

## Open Questions

- [ ] Should `reprompt trends` auto-run `reprompt scan` first if no recent data exists?
- [ ] Should effectiveness scores be visible by default in `reprompt library` or opt-in?
- [ ] Should the MCP server have a `--port` option for SSE transport in addition to stdio?
- [ ] Should `reprompt digest` send notifications (macOS notification center, terminal bell)?
- [ ] Should curated prompts from consolidation be exportable to a portable format (YAML/JSON)?
- [ ] What is the right default similarity threshold for consolidation (0.5 vs 0.6 vs 0.7)?

---

## Success Criteria

1. **Daily active usage:** User runs `reprompt` at least once per working day (measurable via
   `digest_log` and `prompt_snapshots` tables)
2. **Trend awareness:** User can articulate how their prompting changed over the past month
   (qualitative, validated by `trends` showing meaningful deltas)
3. **Pattern reuse:** MCP server surfaces relevant past prompts at least 3x per week
   (measurable via `prompt_feedback` table)
4. **Library hygiene:** Curated prompt count grows while raw duplicate count shrinks
   (measurable via `curated_prompts` vs `prompts WHERE duplicate_of IS NOT NULL`)
5. **Retention loop completion:** The hook-triggered digest creates a "check-in" habit where
   users look at their weekly progress without being prompted by another human
