# `reprompt distill` — Conversation Distillation Design

## Goal

Extract the most important turns from an AI coding conversation, filtering noise and surfacing key decisions. Rule-based (Layer 1, open-source), with a plugin interface for future LLM-powered summarization (Layer 2, Pro).

## Problem Statement

AI power users run 20–50+ turn conversations daily. When context windows fill up, they need to know: "What actually mattered in this session?" No existing tool provides conversation-level distillation locally, without sending data to a server.

**User stories:**
- "I had a 40-turn Claude Code session. What were the key decisions?"
- "Copy the important parts of my last conversation so I can paste them into a new session."
- "Show me which turns triggered the most work."

## Architecture

```
Raw session file → parse_conversation() → list[ConversationTurn]
                                              ↓
                              DB enrichment (scores, dedup status)
                                              ↓
                              Turn importance scoring (6 signals)
                                              ↓
                              Filtering (threshold ≥ 0.3)
                                              ↓
                              Turn pairing (user + assistant pairs)
                                              ↓
                              Output (filtered / summary / json / clipboard)
```

### Data Source: Hybrid Approach

- **Raw session files** provide full conversation (user + assistant turns, tool_use, timestamps).
- **DB tables** provide enrichment (prompt scores from `prompt_features`, dedup status from `prompts`, session metadata from `session_meta`).
- Session files are located via the `processed_sessions` table which maps `file_path → source`.

This avoids storing conversation data twice while getting the full picture.

## Data Model

### ConversationTurn

```python
@dataclass
class ConversationTurn:
    role: str              # "user" | "assistant"
    text: str              # The actual content
    timestamp: str         # ISO timestamp
    turn_index: int        # 0-based position in conversation

    # Assistant-specific (0/False for user turns)
    tool_calls: int = 0    # Number of tool_use blocks in this turn
    has_error: bool = False # Whether turn contains error/failure
    tool_use_paths: list[str] = field(default_factory=list)  # File paths from tool_use blocks

    # Enrichment (populated by distill engine, not adapter)
    score: float | None = None         # Display-only, from prompt_features (see Enrichment)
    is_duplicate: bool = False          # Cross-referenced with dedup
    importance: float = 0.0            # Computed by distill scoring (6 signals only)
```

**Note on `score` field:** This is **display-only enrichment data** — it does NOT feed into the 6-signal importance calculation. It is populated opportunistically from `prompt_features` (see Enrichment section) and shown in JSON output for reference. The `importance` field is the sole ranking signal.

### Conversation

```python
@dataclass
class Conversation:
    session_id: str
    source: str
    project: str | None
    turns: list[ConversationTurn]
    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: int | None = None  # Computed from timestamps (see Duration)
```

### DistillResult

```python
@dataclass
class DistillResult:
    conversation: Conversation       # Original full conversation
    filtered_turns: list[ConversationTurn]  # Turns above threshold
    threshold: float                 # Importance threshold used
    summary: str | None = None       # Generated if --summary
    files_changed: list[str] = field(default_factory=list)  # Extracted from tool_use
    stats: DistillStats = field(default_factory=DistillStats)

@dataclass
class DistillStats:
    total_turns: int = 0
    kept_turns: int = 0
    retention_ratio: float = 0.0     # kept/total (0.26 = kept 26% of turns)
    total_duration_seconds: int = 0
```

## Turn Importance Scoring

Six weighted signals, all rule-based (no LLM):

| Signal | Weight | Computation | Rationale |
|--------|--------|-------------|-----------|
| **Position** | 0.15 | First turn = 1.0, last turn = 0.8, others = 0.3 + 0.2 * recency | First turn sets context, last is conclusion |
| **Length** | 0.15 | `min(char_count / median_length, 1.0)` | Longer turns tend to be more substantive |
| **Tool trigger** | 0.20 | `min(tool_calls / 5, 1.0)` on the assistant turn following this user turn | Turns causing lots of tool use = key decisions |
| **Error recovery** | 0.15 | 1.0 if previous assistant turn has `has_error=True` | User correcting course = high-value context |
| **Semantic shift** | 0.20 | TF-IDF cosine distance from previous user turn; 0.5 (neutral) if first turn | Topic changes mark decision boundaries |
| **Uniqueness** | 0.15 | 1.0 - (similarity to most similar earlier turn via TF-IDF) | Novel instructions > repetitive ones |

**Scoring rules:**
- User turns: scored by all 6 signals → `importance = weighted sum`
- Assistant turns: derived score = average of adjacent user turns' importance
- Minimum threshold: 0.3 (configurable via `--threshold`)

### Tool Trigger Pairing

The tool_trigger signal requires pairing user turns with their assistant responses. For user turn at index `i`, the tool_calls come from the assistant turn at index `i+1` (if it exists and role == "assistant").

### Semantic Shift Computation

Uses scikit-learn `TfidfVectorizer` (already a dependency) fitted on all user turn texts in the conversation. Cosine distance between consecutive user turns. First user turn gets semantic_shift = 0.5 (neutral).

## DB Enrichment

Enrichment is **opportunistic** — it enhances output when data exists, but distill works fully without it.

**Score enrichment:** For each user turn, compute `hashlib.sha256(text.strip().encode()).hexdigest()` (same algorithm as `Prompt.__post_init__`). Look up the hash in `prompt_features`. If found, populate `ConversationTurn.score` with `overall_score`. If not found (user never ran `reprompt score` on this text), leave as `None`. This field is display-only and does NOT affect the 6-signal importance calculation.

**Dedup enrichment:** Same hash lookup in `prompts` table. If `duplicate_of IS NOT NULL`, set `is_duplicate = True`. This is informational — the uniqueness signal in scoring uses TF-IDF similarity within the conversation, not the DB dedup status.

### Duration Computation

`Conversation.duration_seconds` is derived from the first and last timestamps in `turns`:
```python
from datetime import datetime
start = datetime.fromisoformat(turns[0].timestamp.replace("Z", "+00:00"))
end = datetime.fromisoformat(turns[-1].timestamp.replace("Z", "+00:00"))
duration_seconds = int((end - start).total_seconds())
```
This follows the same `fromisoformat` + Z-replacement pattern used in `claude_code.py:parse_session_meta()`.

## Turn Pairing in Output

Filtered output shows **user-assistant pairs**, not isolated turns. When a user turn passes the threshold, its corresponding assistant response is always included (preserves conversation coherence). Assistant-only turns below threshold are dropped only if their adjacent user turns are also below threshold.

## Adapter Integration

### Base class (additive, non-breaking)

```python
# adapters/base.py
class BaseAdapter(ABC):
    @abstractmethod
    def parse_session(self, path: Path) -> list[Prompt]: ...

    def parse_conversation(self, path: Path) -> list[ConversationTurn]:
        """Parse full conversation with both roles.
        Default: user-only turns from parse_session()."""
        prompts = self.parse_session(path)
        return [
            ConversationTurn(
                role="user", text=p.text, timestamp=p.timestamp, turn_index=i
            )
            for i, p in enumerate(prompts)
        ]
```

### v1.3.0 adapters with full parse_conversation()

| Adapter | Approach |
|---------|----------|
| **claude-code** | Iterate JSONL entries. `type=user` + `role=user` → user turn. `type=assistant` → assistant turn. Count `tool_use` content blocks. Detect errors from `is_error` field or error-related content. |
| **chatgpt-export** | Walk `mapping` tree in order for a single conversation (selected by `conv_id`). `author.role=user` → user turn. `author.role=assistant` → assistant turn. No tool_calls data (set to 0). Accepts optional `conv_id` parameter; if None, parses first conversation in file. |

### Future adapters (v1.3.1+)

claude-chat, aider, gemini, openclaw, cline — implement `parse_conversation()` as data becomes available. They fall back to user-only via base class until then.

## Session Resolution

How `distill` finds which session file to parse:

| Input | Resolution |
|-------|-----------|
| `--last N` | Query `processed_sessions` ordered by `processed_at DESC`, take first N. Return list of `(file_path, source)`. |
| `<session_id>` | Query `prompts` for matching `session_id`, get `source`. Reconstruct file path: `adapter.default_session_path / session_id + ext` (e.g. `.jsonl` for claude-code). Verify file exists. If not, fall back to `processed_sessions WHERE file_path LIKE '%' || session_id || '%'`. |
| `--source X` | Filter `processed_sessions` by source, then apply `--last` logic. |

**Edge case — file deleted:** If session file no longer exists on disk, distill falls back to DB-only mode: query `prompts WHERE session_id = ?` for user turns (no assistant turns, no tool_use data). Warn user: "Session file not found, showing user turns only."

### ChatGPT Session Resolution

ChatGPT exports contain multiple conversations in one `conversations.json` file. The `session_id` for ChatGPT prompts is a hash-based string (e.g. `chatgpt-20260323T100000-ab1c2d3e`). When `distill` receives a ChatGPT session_id:

1. Look up `source = "chatgpt-export"` from `prompts` table
2. Find the `conversations.json` file path from `processed_sessions`
3. Parse the file, iterate conversation objects, match by `conv_id` (computed same way as in `chatgpt.py:_make_session_id()`)
4. Call `parse_conversation()` on that single conversation object

The ChatGPT `parse_conversation()` accepts an optional `conv_id` parameter to select a specific conversation from the file.

## Output Modes

### Tier 1 — Filtered conversation (default)

```
╭─ Distill: session abc123 (claude-code) ─╮
│ Project: reprompt | 45min | 47 → 12 turns │
╰──────────────────────────────────────────╯

★★★ [T1] User:
  根据我们的设计文档继续我们的任务
  Assistant: I'll read the spec and continue with Task 5...

★★☆ [T8] User:
  不对，用approach B，parse_session不要改
  Assistant: You're right, creating separate parse_conversation()...

★★★ [T15] User:
  测试通过了，commit吧
  Assistant: Committed: feat: add conversation parser
```

Stars: ★★★ = importance ≥ 0.7, ★★☆ = ≥ 0.5, ★☆☆ = ≥ 0.3

Assistant text truncated to first 80 chars in terminal mode (full in JSON).

### Tier 2 — Summary (`--summary`)

```
╭─ Session Summary: abc123 ─╮

This session implemented the conversation parser for the distill feature.

Key decisions:
  • Created separate parse_conversation() instead of modifying parse_session()
  • Used weighted scoring with 6 signals for turn importance
  • Threshold set at 0.3 for filtering

Files changed: core/distill.py, adapters/base.py, tests/test_distill.py

47 turns → 12 key turns | 45min | claude-code
╰───────────────────────────╯
```

Summary is rule-based:
1. **Description**: First user turn text (compressed via `compress_text()`) + project name
2. **Key decisions**: Top 5 user turns by importance, each compressed
3. **Files changed**: Flattened from `tool_use_paths` across all assistant turns (deduplicated, sorted). Only Edit/Write paths included (Read paths are noise).
4. **Stats**: Turn counts + duration + source

### Tier 3 — JSON (`--json`)

```json
{
  "session_id": "abc123",
  "source": "claude-code",
  "project": "reprompt",
  "duration_seconds": 2700,
  "total_turns": 47,
  "kept_turns": 12,
  "retention_ratio": 0.26,
  "threshold": 0.3,
  "summary": "...",
  "files_changed": ["core/distill.py", "adapters/base.py"],
  "turns": [
    {
      "turn_index": 0,
      "role": "user",
      "text": "...",
      "timestamp": "2026-03-23T10:00:00Z",
      "importance": 0.85,
      "tool_calls": 0
    }
  ]
}
```

## CLI Interface

```
reprompt distill                           # Default: most recent session
reprompt distill --last 3                  # Last 3 sessions
reprompt distill --summary                 # Key decisions only
reprompt distill --copy                    # Filtered → clipboard
reprompt distill --json                    # Machine-readable
reprompt distill abc123                    # By session ID
reprompt distill --source chatgpt-export   # Filter by adapter
reprompt distill --threshold 0.5           # Stricter filtering
reprompt distill --last 3 --copy           # Last 3, concatenated to clipboard
```

### Flag Details

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--last` | `int` | 1 | Most recent N sessions. Always requires explicit value. |
| `--source` | `str` | None | Filter by adapter name |
| `--summary` | `bool` | False | Tier 2 compressed output |
| `--json` | `bool` | False | JSON output |
| `--copy` | `bool` | False | Copy to clipboard |
| `--threshold` | `float` | 0.3 | Importance cutoff (0.0–1.0) |
| `session_id` | `str` (positional, optional) | None | Specific session |

`session_id` and `--last` are mutually exclusive. If neither is provided, default behavior is `--last 1` (most recent session).

**Multi-session behavior (`--last N`):** Each session is distilled independently. Terminal output separates sessions with a horizontal rule. `--copy` concatenates all sessions (separated by `---`). `--json` outputs a JSON array of DistillResult objects.

## File Structure

| File | Responsibility |
|------|----------------|
| `core/conversation.py` | `ConversationTurn`, `Conversation`, `DistillResult`, `DistillStats` dataclasses |
| `core/distill.py` | `distill_conversation(conv, threshold) → DistillResult` — scoring engine, filtering, summary |
| `adapters/base.py` | Add `parse_conversation()` default method |
| `adapters/claude_code.py` | Override `parse_conversation()` with full JSONL parsing |
| `adapters/chatgpt.py` | Override `parse_conversation()` with tree-walk parsing |
| `output/distill_terminal.py` | `render_distill(result) → str` Rich terminal output |
| `cli.py` | `distill` command registration |

## DB Changes

**None.** Distill reads from existing tables:
- `processed_sessions` — file path + source lookup
- `prompt_features` — optional score enrichment
- `prompts` — dedup status, fallback if file missing

No new tables, no migrations.

## Pro Plugin Interface (Layer 2, future)

```python
# Entry point group: "reprompt.distill_backends"
# Interface:
def distill_llm(conversation: Conversation) -> str:
    """Returns LLM-generated semantic summary.
    Example: '20 turns about auth → decided JWT with refresh tokens'
    """
```

When `reprompt-pro` is installed and user passes `--mode llm`:
- Plugin registered via `entry_points`
- Falls back gracefully: "LLM distillation requires reprompt-pro. Install: pip install reprompt-pro"

## Testing Strategy

| Test file | Coverage |
|-----------|----------|
| `tests/test_conversation.py` | Dataclass construction, field defaults, validation |
| `tests/test_distill.py` | Scoring signals (each independently), filtering, summary generation, edge cases (empty conversation, single turn, all below threshold) |
| `tests/test_distill_cli.py` | CLI invocation, --last, --json, --summary, --copy, --threshold, session_id |
| `tests/test_parse_conversation_claude.py` | Claude Code parse_conversation() with sample JSONL |
| `tests/test_parse_conversation_chatgpt.py` | ChatGPT parse_conversation() with sample JSON, conv_id selection |

**Additional edge case tests (in test_distill.py and test_distill_cli.py):**
- Session file deleted → DB-only fallback (user turns only, warning message)
- `--last 3` multi-session → each session distilled independently, separated output
- `--copy` with `--last 3` → concatenated with `---` separator
- Empty conversation (0 turns) → graceful empty result
- Single-turn conversation → that turn always passes threshold
- All turns below threshold → empty filtered_turns with stats showing 0 kept

**Test data:** Synthetic JSONL/JSON fixtures embedded in test files (same pattern as existing adapter tests).

## Success Criteria

1. `reprompt distill --last` produces a useful filtered view of the most recent session
2. 47-turn conversation distilled to ~10-15 key turns (70-80% reduction)
3. Error-recovery turns and topic-shift turns are consistently ranked high
4. `--copy` puts clipboard-ready text that can be pasted into a new AI session
5. Works with both Claude Code and ChatGPT exports
6. Zero new dependencies (uses existing scikit-learn for TF-IDF)
7. All tests pass, no regressions in existing 1153 tests
