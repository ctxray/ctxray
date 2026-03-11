# reprompt Roadmap

> Last updated: 2026-03-11

## Vision

reprompt is the **prompt analytics** tool for AI coding sessions — understand your patterns, improve your prompting, track your progress. Zero-config, privacy-first, CLI-first.

---

## Current State (v0.5)

### Adapters (6)
- Claude Code, OpenClaw, Cursor IDE, Aider, Gemini CLI, Cline

### Analysis
- Two-layer dedup (SHA-256 + TF-IDF cosine similarity)
- TF-IDF hot phrase extraction, K-means clustering
- Auto-categorization (debug/implement/test/review/refactor)
- Session effectiveness scoring (composite: tool calls, errors, specificity)
- Prompt merge-view (similar prompt clustering with canonical selection)

### Commands
- `reprompt scan` — extract prompts from AI session files
- `reprompt report` — full analytics dashboard (terminal or `--html`)
- `reprompt library` — organized prompt collection by category
- `reprompt trends` — specificity and vocabulary evolution over time
- `reprompt recommend` — personalized improvement suggestions
- `reprompt effectiveness` — session quality scores
- `reprompt merge-view` — similar prompt clusters
- `reprompt save` / `reprompt templates` — save and reuse best prompts
- `reprompt lint` — prompt quality checks (CI-ready)
- `reprompt search` — full-text prompt search
- `reprompt demo` — try with sample data

### Integration
- MCP server for IDE integration
- GitHub Action (`action.yml`) for CI prompt quality checks
- JSON output on all commands for pipeline integration

---

## Next Up

### More Adapters

Each adapter is ~50 lines implementing `BaseAdapter.parse_session()`. Community contributions welcome.

| Tool | Status | Priority |
|------|--------|----------|
| Claude Code | ✅ Shipped | — |
| OpenClaw | ✅ Shipped | — |
| Cursor IDE | ✅ Shipped | — |
| Aider | ✅ Shipped | — |
| Gemini CLI | ✅ Shipped | — |
| Cline | ✅ Shipped | — |
| GitHub Copilot Chat | Planned | High |
| Continue.dev | Planned | Medium |
| Windsurf | Planned | Medium |

### Style Analysis

`reprompt style` — extract your prompting style fingerprint:
- Average length, vocabulary level, structure patterns
- Preferred categories and opening patterns
- Specificity habits (file names, line numbers, function names)
- Pure analysis, no LLM needed

### Template Variables

Extend `reprompt save` with `{variable}` placeholders:
```bash
reprompt save --name "debug-specific" \
  "Debug {file} — {function} returns {actual} instead of {expected}"

reprompt use debug-specific file=auth.py function=login actual=401 expected=200
```

### Enhanced Lint Rules

Expand `reprompt lint` with configurable rules:
- Custom rule definitions in `.reprompt.yml`
- Per-project and per-team configurations
- More built-in rules (implement needs acceptance criteria, test needs target, etc.)

---

## Competitive Landscape (2026-03)

**No direct competitor exists.** reprompt is the only open-source tool that does CLI-first algorithmic analysis of AI coding prompts.

| Tool | Stars | What It Does | How reprompt Differs |
|------|-------|-------------|---------------------|
| **promptfoo** | 10.8K | LLM output testing & evaluation | Tests LLM responses, not developer prompts |
| **DSPy** | 20K+ | Prompt programming framework | Optimizes LLM app prompts, not coding sessions |
| **Langfuse** | — | LLM observability platform | Server-side tracing, not local CLI |
| **Vibe-Log** | — | Claude session summaries | LLM-based (expensive, non-reproducible) |

---

## Architecture Principles

1. **Zero-config first** — Every feature works without LLM by default
2. **Privacy by design** — All data stays local
3. **Adapter pattern** — New AI tools supported by adding ~50 lines
4. **CLI first, GUI second** — Terminal is primary, HTML dashboard is secondary
5. **Composable** — Every command supports JSON output for piping

---

## How to Contribute

Small contributions welcome:
- **New adapter** (~50 lines) — see `src/reprompt/adapters/base.py`
- **New lint rules** — see `src/reprompt/core/lint.py`
- **Better categorization** — improve keyword rules in `core/library.py`
- **Documentation and examples**

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.
