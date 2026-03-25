# reprompt Roadmap

> Last updated: 2026-03-24 · Current version: v1.4.0

## Vision

reprompt is the **prompt intelligence** tool for AI sessions — distill your conversations, compress your prompts, score them against research, and track your progress. Zero-config, privacy-first, CLI-first.

**Category definition:** reprompt analyzes *human inputs* (how you prompt), not *LLM outputs* (how models respond). Every other tool in the eval/observability space — Promptfoo, Braintrust, DeepEval, Langfuse — answers "did my AI system answer correctly?" reprompt answers "am I asking well?" This is an unoccupied category.

---

## Current State (v1.4.0) — Production Stable

### Adapters (8)
Claude Code · OpenClaw · Cursor IDE · Aider · Gemini CLI · Cline · ChatGPT · Claude.ai

### Commands (23 visible, 5 deprecated)
`scan` · `import` · `report` · `library` · `trends` · `recommend` · `template [save|list|use]` · `lint` · `search` · `demo` · `status` · `purge` · `install-hook` · `install-extension` · `extension-status` · `score` · `compare` · `insights` · `digest` · `style` · `wrapped` · `telemetry` · `mcp-serve` · `compress` · `distill` · `privacy`

### Integrations
- MCP server (`reprompt mcp-serve`) for IDE integration
- GitHub Action (`action.yml`) for CI prompt quality checks
- HTML dashboard (`reprompt report --html`)
- Browser extension (Chrome/Firefox) via Native Messaging bridge
- JSON output on all commands for pipeline integration

### Key Features by Version

| Version | Feature | Description |
|---------|---------|-------------|
| v1.0.0 | Core platform | Scoring, dedup, report, trends, digest, style, effectiveness, templates, MCP, HTML dashboard |
| v1.1.0 | Privacy exposure | `reprompt privacy` — where your prompts went, training risk analysis |
| v1.2.0 | Prompt compression | `reprompt compress` — 4-layer rule-based compression (43 zh + 51 en rules) |
| v1.3.0 | Conversation distillation | `reprompt distill` — 6-signal importance scoring for conversation turns |
| v1.3.1 | UX polish | Actionable suggestions on 5 commands, `--source` filter on all data commands |
| v1.4.0 | Context recovery + consolidation | `distill --export` context document, signal transparency, command consolidation (27→23) |

### Quality
- 1295 tests, ≥90% coverage
- Strict mypy, ruff lint/format
- CI: coverage gate + pre-publish test step
- Stable public API (`score_prompt`, `compare_prompts`, `extract_features`)

---

## v1.4 — Context Recovery + Command Consolidation

| Priority | Item | Rationale |
|----------|------|-----------|
| P1 | `distill --export` context recovery | **DONE** — community signal: resume sessions after compaction/timeout |
| P2 | Command consolidation: `save`/`templates`/`use` → `template [save\|list\|use]` | **DONE** — 3 commands doing 1 thing = cognitive overload |
| P2 | Command consolidation: `effectiveness`/`merge-view` → `insights` sub-insights | **DONE** — concepts unclear to users |
| P3 | `style` shows change trends | "specificity +12% this week" drives revisits |
| P4 | `distill --show-weights` / `--weights` signal transparency | Community request for weight visibility |
| P5 | `compare --best-worst` auto-pick | Auto-pick best/worst from DB |
| P5 | `--copy` as standard option on remaining commands | Consistency |

**Status: 27 → 23 visible commands. P1+P2 shipped. Context recovery + consolidation done.**

---

## v1.5+ — Future Work

| Feature | Description |
|---------|-------------|
| Sensitive content detection | Privacy narrative; PII in prompts |
| Agent workflow analysis | Multi-step agent session patterns |
| `.reprompt.yml` configurable lint | Team/Pro direction |
| `reprompt suggest` (Ollama rewrite) | LLM-powered prompt improvement |
| Homebrew formula | `brew install reprompt` |
| More adapters | Perplexity, Mistral, Grok, Gemini Takeout |
| Windows Native Messaging | Extension support on Windows |

---

## Architecture Principles

1. **Zero-config first** — Every feature works without LLM by default
2. **Privacy by design** — All data stays local; extension has zero server
3. **Adapter pattern** — New AI tools supported by adding ~50 lines
4. **Input not output** — We analyze human prompts (inputs); LLM eval tools analyze model responses (outputs)
5. **CLI first, GUI second** — Terminal is primary, HTML dashboard is secondary
6. **Composable** — Every command supports JSON output for piping

---

## How to Contribute

- **New adapter** (~50 lines) — see `src/reprompt/adapters/base.py`
- **New lint rules** — see `src/reprompt/core/lint.py`
- **Better categorization** — improve keyword rules in `core/library.py`
- **Browser extension** — see `reprompt-extension` repo

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.
