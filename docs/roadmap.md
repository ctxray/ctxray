# reprompt Roadmap

> Last updated: 2026-03-11

## Vision

reprompt evolves from **prompt analytics** (understand your patterns) → **prompt intelligence** (learn your style, suggest improvements) → **prompt copilot** (generate and optimize prompts for you).

Each phase builds on the previous. No phase requires the next to be valuable on its own.

---

## Current State (v0.3)

What we ship today:
- Scan sessions from Claude Code, OpenClaw, Cursor IDE
- Two-layer dedup (SHA-256 + TF-IDF cosine)
- TF-IDF hot phrase extraction, K-means clustering
- Auto-categorization (debug/implement/test/review/refactor)
- Prompt library (organized by category)
- Trends tracking (specificity, vocabulary breadth)
- Recommendations (effectiveness scoring, improvement tips)
- HTML interactive dashboard (`reprompt report --html`)
- Demo mode with realistic sample data
- MCP server for IDE integration

---

## Phase 1: Better Analytics (v0.4)

**Theme:** Make the existing data more actionable. No LLM needed.

### 1.1 Prompt Merge View ("合并同类项")

**Problem:** Users see dedup stats but can't see WHICH prompts are similar. They know 32% are near-duplicates but can't act on it.

**Solution:** `reprompt merge-view` — shows clusters of semantically similar prompts side by side:

```
Cluster: Authentication Debugging (5 prompts)
  ├─ "fix the auth bug"                           (2026-02-15)
  ├─ "fix the authentication issue"                (2026-02-18)
  ├─ "debug auth — login returns 401"              (2026-02-22)  ← most specific
  ├─ "fix auth middleware"                         (2026-03-01)
  └─ "the auth is broken again"                    (2026-03-05)

  → Recommended canonical: "debug auth — login returns 401"
  → You could reuse this instead of writing a new one each time
```

**Implementation:**
- Already have TF-IDF cosine similarity + K-means clusters
- Add: cluster member listing, chronological sorting, "best in cluster" selection (longest + most specific)
- Output: terminal table, HTML section in dashboard, JSON
- New command: `reprompt merge-view` or integrated into `reprompt library`

**Why first:** Pure algorithmic extension of existing code. High user value. Visual proof of "you keep repeating yourself."

### 1.2 Prompt Templates / Snippets

**Problem:** After seeing their best prompts, users want to save and reuse them.

**Solution:** `reprompt save <prompt-text>` and `reprompt templates` — personal prompt template library with variables:

```
reprompt save --name "debug-specific" \
  "Debug {file} — {function} returns {actual} instead of {expected}"

reprompt templates
# Shows:
#   1. debug-specific: "Debug {file} — {function} returns..."
#   2. implement-with-tests: "Implement {feature} with unit tests..."

reprompt use debug-specific file=auth.py function=login actual=401 expected=200
# Outputs: "Debug auth.py — login returns 401 instead of 200"
# (copies to clipboard)
```

**Implementation:**
- New SQLite table: `prompt_templates (id, name, template_text, category, usage_count, created_at)`
- Auto-suggest: after merge-view, suggest saving the "best" prompt from each cluster as a template
- Variable substitution: simple `{var}` regex replacement

### 1.3 Session Effectiveness Scoring

**Problem:** "Which prompts work well" is vague. Need a concrete metric.

**Solution:** Score each prompt session by:
- Session length (fewer back-and-forth = more effective prompt)
- Whether the task was completed (heuristic: session ended vs abandoned)
- Prompt specificity (length, named entities, file references)

Combined into 0-1 effectiveness score. Already partially implemented in `recommend` — extend it.

### 1.4 Adapter Expansion

Add adapters for:
- **GitHub Copilot Chat** — VS Code chat history
- **Windsurf** — if session format is documented
- **Aider** — markdown chat logs
- **Continue.dev** — session history

Each adapter is ~50 lines implementing `BaseAdapter.parse_session()`. Low effort, high reach.

---

## Phase 2: Local Prompt Intelligence (v0.5)

**Theme:** Use local LLM (optional) to understand prompt intent and generate suggestions. Everything stays on-device.

### 2.1 Prompt Style Engine

**Problem:** Users have a prompting style but can't articulate it. They want new prompts that "sound like them."

**Solution:**
1. Analyze user's prompt history → extract style fingerprint:
   - Average length, vocabulary level, structure patterns
   - Preferred categories, common opening patterns ("fix...", "add...", "refactor...")
   - Level of specificity, use of file names/line numbers
2. When user faces a new task: `reprompt draft "add pagination to search"`
   → generates a prompt IN THEIR STYLE with appropriate specificity

**Implementation:**
- Style extraction: TF-IDF on user's top prompts (no LLM needed for basic version)
- Advanced version: local LLM (Ollama) few-shot with user's best prompts as examples
- Output: suggested prompt text, copied to clipboard

### 2.2 Smart Recommendations (Local LLM)

**Problem:** Current `recommend` uses rules. LLM can give nuanced, contextual advice.

**Solution:** `reprompt recommend --smart`
- Feeds user's prompt patterns + effectiveness scores to local LLM
- Gets personalized advice: "Your debug prompts lack file context. Here's how to improve: [example based on your actual code patterns]"
- Opt-in, requires Ollama

### 2.3 Prompt Intent Tagging

**Problem:** Auto-categorization is keyword-based (regex). Misses nuance.

**Solution:** Local LLM classifies prompts with richer intent tags:
- `debug:authentication`, `implement:pagination`, `refactor:extract-method`
- Sub-categories enable finer analysis
- Fallback to keyword categorization when no LLM available

### 2.4 Interactive Brainstorm Mode

**Problem:** User faces a new task and doesn't know how to prompt effectively.

**Solution:** `reprompt brainstorm "build a rate limiter"`
- Shows 3-5 prompt variations at different specificity levels
- Uses user's style + best practices
- Interactive: user picks one, refines, saves as template

```
reprompt brainstorm "add rate limiting"

Generating prompt variations...

  1. [Quick]    "Add rate limiting to the API"
  2. [Moderate] "Add rate limiting to the Express API endpoints —
                 use sliding window algorithm, 100 req/min per IP"
  3. [Detailed] "Implement rate limiting middleware for the Express API:
                 - Sliding window counter (Redis-backed)
                 - Default: 100 requests/minute per IP
                 - Return 429 with Retry-After header
                 - Exempt /health and /metrics endpoints
                 - Add rate limit headers (X-RateLimit-*) to responses
                 - Include unit tests for window rollover edge cases"

  Pick [1-3] to copy, or [r]efine:
```

**Implementation:**
- Basic version: template-based generation from patterns (no LLM)
- Advanced version: local LLM with few-shot examples from user history
- Always local, always optional

---

## Phase 3: Connected Intelligence (v0.6+)

**Theme:** Opt-in online features. Community wisdom. Still privacy-first.

### 3.1 Community Prompt Patterns

**Problem:** Individual prompt data is limited. Community patterns are more robust.

**Solution:** Anonymous, aggregated prompt patterns shared publicly:
- "For debugging tasks, prompts with file names are 3x more effective" (aggregated stat)
- No individual prompts shared — only statistical patterns
- Opt-in contribution: `reprompt contribute --anonymous`
- Published as open dataset on GitHub

### 3.2 Prompt Optimizer (Web-Enhanced)

**Problem:** User writes a mediocre prompt. How to make it better?

**Solution:** `reprompt optimize "fix the bug"`
1. Analyze prompt category and intent
2. Search web for best practices for that category
3. Fetch community patterns for similar prompts
4. Generate optimized version with explanations

```
reprompt optimize "fix the bug"

Original:  "fix the bug"
Category:  debug (low specificity: 0.12)

Suggestions:
  1. Add the filename:     "fix the bug in auth.py"
  2. Add the function:     "fix the login() bug in auth.py"
  3. Add expected behavior: "fix login() in auth.py — should return
                            JWT token but returns None for valid credentials"
  4. Add error context:    "fix login() in auth.py — TypeError: 'NoneType'
                            has no attribute 'encode' on line 42. Should
                            return JWT token for valid credentials."

Each level adds ~15% effectiveness based on community patterns.
```

### 3.3 Prompt CI / Quality Gate

**Problem:** Teams want consistent prompt quality across developers.

**Solution:** `reprompt lint` as CI check:
- Configurable rules: min length, must include file reference for debug, etc.
- Team prompt library: shared templates in `.reprompt/templates/`
- Pre-commit hook: warns on low-specificity prompts
- Dashboard for team analytics

### 3.4 IDE Integration (Deep)

Beyond MCP server:
- VS Code extension: inline prompt suggestions as you type in AI chat
- Clipboard integration: `reprompt watch` monitors clipboard, suggests improvements
- Shell integration: `reprompt wrap "fix the bug"` → optimizes, then passes to Claude Code

---

## Prioritization Framework

Each feature scored on:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| User Value | 40% | How much does this help users? |
| Effort | 25% | How hard to build? (inverse) |
| Differentiation | 20% | Does this exist elsewhere? |
| Community | 15% | Will this drive GitHub stars/contributions? |

### Priority Matrix

| Feature | Value | Effort | Diff | Community | **Score** | Phase |
|---------|-------|--------|------|-----------|-----------|-------|
| Merge View | 9 | 8 | 8 | 7 | **8.3** | 1.1 |
| Prompt Templates | 8 | 8 | 6 | 7 | **7.5** | 1.2 |
| Adapter Expansion | 7 | 9 | 5 | 9 | **7.4** | 1.4 |
| Brainstorm Mode | 9 | 6 | 9 | 8 | **8.1** | 2.4 |
| Prompt Optimizer | 9 | 5 | 9 | 8 | **7.8** | 3.2 |
| Style Engine | 8 | 5 | 9 | 7 | **7.3** | 2.1 |
| Session Scoring | 7 | 7 | 6 | 5 | **6.6** | 1.3 |
| Community Patterns | 8 | 4 | 8 | 9 | **7.2** | 3.1 |
| Prompt CI | 7 | 5 | 7 | 8 | **6.7** | 3.3 |
| IDE Extension | 8 | 3 | 7 | 9 | **6.7** | 3.4 |

### Recommended Build Order

```
v0.4 (2-3 weeks)          v0.5 (4-6 weeks)           v0.6+ (ongoing)
━━━━━━━━━━━━━━━━━━━━      ━━━━━━━━━━━━━━━━━━━━━      ━━━━━━━━━━━━━━━━━━━━━
1. Merge View              5. Brainstorm Mode          8. Prompt Optimizer
2. Prompt Templates         6. Style Engine             9. Community Patterns
3. Adapter Expansion        7. Smart Recommendations   10. Prompt CI
4. Session Scoring                                     11. IDE Extension
```

---

## Architecture Principles

1. **Zero-config first** — Every feature works without LLM by default (TF-IDF, rules, templates)
2. **LLM optional** — Ollama/local model enhances but never required
3. **Privacy by design** — All data local. Online features opt-in and anonymized
4. **Adapter pattern** — New AI tools supported by adding ~50 lines
5. **CLI first, GUI second** — Terminal is primary, HTML dashboard is secondary
6. **Composable** — Each command is pipeable (`reprompt optimize "..." | pbcopy`)

---

## Open Questions for Community

- Should templates be per-project or global?
- What effectiveness metric matters most? (session length, completion, user rating?)
- Which AI tools should we prioritize adapters for?
- Is team/enterprise prompt analytics a direction worth exploring?

---

## How to Contribute

Each feature above maps to a GitHub Issue. Pick one, discuss in the issue, submit a PR.

Small contributions welcome:
- New adapter (~50 lines)
- New categorization rules
- Better effectiveness heuristics
- Documentation and examples
