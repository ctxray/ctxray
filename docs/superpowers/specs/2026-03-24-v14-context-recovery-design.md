# v1.4 Design Spec: Context Recovery + Consolidation

> **Version:** v1.4.0
> **Date:** 2026-03-24
> **Status:** Draft
> **Community signal:** pvdyck (r/ClaudeAI), LLMDevs commenters, LeadingFarmer3923 (r/ClaudeAI)

---

## Problem

AI coding sessions lose context through compaction, timeouts, and tool-switching. Users are forced to re-explain what they were doing, what decisions were made, and where they left off. This is a daily pain point for every Claude Code, Cursor, and Aider power user.

No tool produces a structured, portable, human-readable distillation of a coding session optimized for re-injection into a new session.

## Solution

Add `--export` flag to the existing `reprompt distill` command. Produces a markdown context document designed to be pasted into any AI tool as session resumption context.

```bash
# Primary workflow
reprompt distill --last 1 --export | pbcopy
# → paste into new Claude Code / Cursor / ChatGPT session

# With clipboard shortcut
reprompt distill --last 1 --export --copy

# Full mode (includes assistant responses)
reprompt distill --last 1 --export --full
```

## Design Principles

1. **Generic markdown** — works in any AI tool, not coupled to one platform
2. **User turns only** by default — the goal is "what the human decided and did," not replaying the conversation
3. **~500 tokens default** — fits comfortably in any context window alongside other context
4. **Lost-in-the-Middle aware** — actionable sections at top and bottom, reference material in the middle (Stanford 2307.03172, MIT 2025 follow-up)
5. **Cache-friendly header** — stable identifiers first, volatile metadata second (arXiv 2601.06007)
6. **Zero-config** — no LLM required, rule-based extraction from existing distill engine

## Export Document Structure

```markdown
# Session Context: <project>

**Source:** <adapter> | **Date:** <YYYY-MM-DD> | **Duration:** <N>min
**Turns:** <total> → <kept> key turns | **~<N> tokens**

## Goal

<first user turn, compressed via compress_text()>

## Current State

<last high-importance user turn, compressed>

## Key Decisions

1. <turn with high semantic_shift — why a choice was made>
2. <turn with high semantic_shift — why a choice was made>
3. ...

## What Was Done

- <turn with high tool_trigger — what was implemented/changed>
- ...

## Files Changed

`file1.py`, `file2.py`, `file3.py`

## Resume

<last turn with forward-looking intent, if detected; omitted otherwise>
```

### Section Design Details

#### Header
- Project name first (stable, cache-friendly), volatile metadata on second line.
- Token count is approximate: `len(output) // 4`. No external tokenizer dependency.

#### Goal
- Source: first user turn (`user_turns[0]`), processed through `compress_text()`.
- Truncated to 200 chars max.
- Always present (every conversation has a first turn).

#### Current State
- Source: last user turn with `importance >= threshold`, compressed.
- Represents where the session ended up, not where it started.
- If same as Goal (single-turn session), this section is omitted.

#### Key Decisions
- Source: user turns sorted by `semantic_shift` signal (descending), top 5.
- These are turns where the user changed direction or made a choice.
- Each entry compressed and truncated to 150 chars.
- Deduplicated against Goal and Current State (no repeats).

#### What Was Done
- Source: user turns sorted by `tool_trigger` signal (descending), top 5.
- These are turns that caused the most tool activity (implementation work).
- Each entry compressed and truncated to 150 chars.
- Deduplicated against Key Decisions (a turn appears in only one section).

#### Files Changed
- Source: existing `_extract_files_changed()` from distill engine.
- Displayed as inline code, comma-separated. Max 10 files shown (aligned with existing `generate_summary()` cap).

#### Resume
- Source: last 3 user turns, checked for forward-looking keywords.
- Keywords: `next`, `todo`, `now let's`, `then`, `after that`, `move on`, `接下来`, `然后`, `下一步`.
- If no forward-looking turn found, section is omitted entirely.
- Not fabricated — only extracted from actual user text.

### Turn Classification Logic

A user turn's primary section is determined by its highest-scoring signal:

| Highest signal | Section |
|---------------|---------|
| `semantic_shift` | Key Decisions |
| `tool_trigger` | What Was Done |
| Both equal | Key Decisions (decision > action) |

Turns used for Goal, Current State, or Resume are excluded from both lists to avoid repetition.

## `--full` Mode

When `--full` is passed, each user turn in Key Decisions and What Was Done includes the paired assistant response summary:

```markdown
## Key Decisions

1. **User:** Used TF-IDF cosine distance for semantic_shift instead of embeddings
   **Result:** Implemented in `_compute_semantic_signals()`, 4 helper functions added
```

Assistant response is summarized as: first sentence of the response text, or "N tool calls, M files changed" if the response is primarily tool use. This roughly doubles token count (~1000-1500 tokens).

## Weight Transparency Flags

Two separate flags (Typer does not support a single option that acts as both bool flag and string option):

```bash
# Show current weights
reprompt distill --show-weights
# position=0.15, length=0.15, tool_trigger=0.20,
# error_recovery=0.15, semantic_shift=0.20, uniqueness=0.15

# Override weights (advanced)
reprompt distill --last 1 --export --weights "semantic_shift=0.4,tool_trigger=0.3"
```

**`--show-weights`** (bool flag): Prints current signal weights and exits. Ignores all other flags.

**`--weights TEXT`** (string option): Parses comma-separated `key=value` pairs, merges with defaults for unspecified keys. Validation:
- Unknown keys (typos like `tool_tigger`) → error with "unknown weight key" message listing valid keys
- Sum != 1.0 → warning printed to stderr, execution continues
- Override applies to this invocation only, does not persist

## Open/Pro Boundary

| Feature | Layer | Rationale |
|---------|-------|-----------|
| `--export` markdown output | **Open** | Rule-based, zero-config, individual tool |
| `--full` user+assistant pairs | **Open** | Same data, different format |
| `--weights` transparency | **Open** | Transparency builds trust |
| LLM-powered semantic summary | **Pro** | Requires Ollama, clear upgrade path |
| Cross-session memory ("what did I discuss about auth across 100 sessions?") | **Pro** | Needs persistent index + embeddings |

If Pro plugin is installed, `--export --summary` uses LLM to produce a condensed 3-sentence brief instead of rule-based extraction. Graceful degradation message if Pro is not installed.

## Architecture

### New Files

| File | Purpose | ~Lines |
|------|---------|--------|
| `output/export.py` | `generate_export(result, full=False) → str` | ~120 |

### Modified Files

| File | Change |
|------|--------|
| `cli.py` | Add `--export`, `--full`, `--show-weights`, `--weights` flags to `distill` command |
| `core/distill.py` | Expose per-signal scores on `ConversationTurn` for section classification; accept optional `weights` dict |
| `core/conversation.py` | Add `signal_scores: dict[str, float]` field to `ConversationTurn` |
| `core/suggestions.py` | Update distill suggestion to mention `--export` |

### Data Flow

```
Session files → Adapter.parse_conversation() → Conversation
  → distill_conversation(conv, threshold, weights?) → DistillResult
    (turns now have per-signal scores in signal_scores dict)
  → generate_export(result, full=False) → str (markdown)
  → stdout / clipboard / file
```

### Key Implementation Details

1. **Per-signal scores on ConversationTurn:** Currently `importance` is a single float (weighted sum). To classify turns into "Key Decisions" vs "What Was Done," we need access to individual signal scores. Add `signal_scores: dict[str, float] = field(default_factory=dict)` to `ConversationTurn`. Populate during scoring inside `distill_conversation()`:

    ```python
    # Inside the user turn scoring loop (after computing all 6 scores):
    user_turn.signal_scores = {
        "position": pos_score,
        "length": len_score,
        "tool_trigger": tool_score,
        "error_recovery": error_score,
        "semantic_shift": shift_score,
        "uniqueness": unique_score,
    }
    user_turn.importance = (
        weights["position"] * pos_score
        + weights["length"] * len_score
        + ...
    )
    ```

2. **`distill_conversation()` new signature:**

    ```python
    def distill_conversation(
        conversation: Conversation,
        threshold: float = 0.3,
        weights: dict[str, float] | None = None,
    ) -> DistillResult:
    ```

    When `weights` is None, use the existing `W_*` module constants as defaults. When provided, merge: `effective = {**DEFAULT_WEIGHTS, **weights}`. Unknown keys are already rejected at the CLI layer (see `--weights` validation).

3. **Forward-looking detection for Resume:** Simple keyword match on last 3 high-importance user turns. Bilingual (en + zh). No NLP dependency.

4. **Token estimation:** `len(output_text) // 4` — rough but sufficient. No external tokenizer.

5. **Deduplication across sections:** Goal turn, Current State turn, and Resume turn are tracked by `turn_index`. Excluded from Key Decisions and What Was Done candidate pools.

6. **`--full` mode assistant summary:** An assistant turn is "primarily tool use" when `tool_calls > 0 and len(text.strip()) < 200`. In that case, summarize as `"{N} tool calls, {M} files changed"`. Otherwise, use the first sentence of the response text (split on `. ` or `\n`, take first element, truncate to 150 chars).

7. **`--export` restricted to single session:** `--export` requires `--last 1` (or a specific session_id). If `--last N` with N > 1 is combined with `--export`, print error: `"--export works with a single session. Use --last 1 or specify a session ID."` and exit.

8. **`--export --json` envelope:** Outputs `{"export": "<markdown string>", "session_id": "...", "source": "...", "tokens": N}`. The markdown is a single string field, not the raw DistillResult.

9. **Empty filtered_turns fallback:** When `filtered_turns` is empty (threshold too high), `generate_export()` falls back to a minimal document using the first and last raw user turns from `conversation.turns`, with a note: `"(No turns above threshold {threshold}. Showing first and last turns.)"`.

10. **Suggestions update:** Replace the `distill` entry in `SUGGESTIONS` dict (`core/suggestions.py` line 10) with: `'reprompt distill --export --copy (context recovery) · reprompt compress "..." (shorten turns)'`. This replaces the current `report` hint (less relevant after distill) with the new `--export` hint, keeping `compress` as the second option.

11. **`--full` without `--export` warning:** If `--full` is passed without `--export`, print a warning to stderr: `"--full has no effect without --export"` and continue normally. Do not error.

## CLI Interface

```
reprompt distill [SESSION_ID] [OPTIONS]

Existing flags (unchanged):
  --last N          Distill N most recent sessions (default: 1)
  --source TEXT     Filter by adapter name
  --summary         Show compressed summary
  --json            Output as JSON
  --copy            Copy to clipboard
  --threshold FLOAT Importance cutoff 0.0-1.0 (default: 0.3)

New flags (v1.4):
  --export          Output as markdown context document for session resumption
  --full            Include assistant responses in export (requires --export)
  --show-weights    Print current signal weights and exit
  --weights TEXT    Override signal weights, e.g. "semantic_shift=0.4,tool_trigger=0.3"
```

Flag interactions:
- `--export` and `--summary` are mutually exclusive (both produce text, different formats)
- `--export` requires single session: `--last 1` or a session_id. Error if `--last N` with N > 1.
- `--export --json` outputs `{"export": "<markdown>", "session_id": "...", "source": "...", "tokens": N}`
- `--export --copy` copies the markdown to clipboard
- `--full` without `--export` is ignored (only affects export format)
- `--show-weights` prints weights and exits (ignores all other flags)
- `--weights "k=v,..."` overrides weights for the current invocation; unknown keys → error

## v1.4 Full Scope (Context Recovery + Consolidation)

| Priority | Item | Type |
|----------|------|------|
| **P1** | `distill --export` context recovery | New feature |
| **P2** | Command consolidation: `save`/`templates`/`use` → `template [save\|list\|use]` | UX cleanup |
| **P2** | Command consolidation: `effectiveness`/`merge-view` → subcommands of `insights` | UX cleanup |
| **P3** | `style` change trends ("specificity +12% this week") | Enhancement |
| **P4** | `distill --weights` signal transparency | Enhancement |
| **P5** | `compare --best-worst` auto-pick | Enhancement |
| **P5** | `--copy` as standard option on remaining commands | Consistency |

**Target: 27 → ~21 commands after consolidation. 1 new flag (`--export`), not 1 new command.**

## Testing Strategy

| Layer | Tests | What |
|-------|-------|------|
| Unit | ~20 | `generate_export()` with various DistillResult shapes (empty, single turn, many turns, no forward-looking, etc.) |
| Unit | ~10 | Per-signal score classification (semantic_shift dominant → Key Decisions, tool_trigger dominant → What Was Done) |
| Unit | ~5 | Forward-looking keyword detection (en + zh) |
| Unit | ~5 | `--weights` parsing and validation |
| Unit | ~5 | Token estimation accuracy |
| Integration | ~5 | `distill --export` end-to-end through CLI |
| Integration | ~3 | `--export --full` vs default comparison |
| Integration | ~2 | `--export --copy` clipboard integration |
| Unit | ~3 | Empty filtered_turns fallback behavior |
| Snapshot | ~3 | Golden file tests for export format stability (fixtures in `tests/fixtures/export/`) |

**~61 new tests. Target: 1298+ total (currently 1237).**

### Snapshot Test Strategy

Golden file fixtures live in `tests/fixtures/export/`. Each fixture is a `.md` file containing the expected export output for a specific DistillResult shape. Tests compare `generate_export()` output against these files. When the export format intentionally changes, fixtures are regenerated with `pytest --update-snapshots` (custom marker).

## Competitive Position

| Tool | What it does | How reprompt differs |
|------|-------------|---------------------|
| continues (`npx continues`) | Cross-tool session handoff (14 tools) | reprompt adds *importance scoring* — not all turns are equal |
| claude-session-restore | Rust-based extraction of everything | reprompt extracts *what matters*, not everything |
| open-mem | LLM-compressed tool outputs | reprompt is rule-based, zero-config, tool-agnostic |
| Cline Memory Bank | Persistent project memory across tasks | reprompt is retrospective analysis, not live state |
| Cognetivy | Structured prompt creation templates | Complementary: Cognetivy = before, reprompt = after |

**Unique value:** reprompt is the only tool that produces an importance-scored, research-calibrated, portable context recovery document from any AI coding session without requiring an LLM.

## Success Criteria

1. `reprompt distill --last 1 --export` produces a markdown document under 600 tokens for a typical 50-turn session
2. The document, when pasted into a new AI session, gives the model enough context to continue the previous task without the user re-explaining
3. Export format is stable (golden file tests prevent accidental changes)
4. Works with all 8 adapters that support `parse_conversation()`

## References

- Stanford "Lost in the Middle" (arXiv 2307.03172) — U-shaped attention, critical info at top/bottom
- "Don't Break the Cache" (arXiv 2601.06007) — stable prefixes for prompt caching
- Anthropic Context Engineering Guide — compaction + structured notes pattern
- OpenAI GPT-4.1 Prompting Guide — section ordering best practices
- Cline new_task tool — structured handoff format (Completed/Current/Next)
- td (marcus/td) — minimalist handoff: done/remaining/decisions/uncertain
- CONTINUITY (duke-of-beans) — decisions as first-class objects
