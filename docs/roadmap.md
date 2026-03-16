# reprompt Roadmap

> Last updated: 2026-03-16 · Current version: v1.0.0

## Vision

reprompt is the **prompt analytics** tool for AI sessions — understand your patterns, improve your prompting, track your progress. Zero-config, privacy-first, CLI-first.

**Category definition:** reprompt analyzes *human inputs* (how you prompt), not *LLM outputs* (how models respond). Every other tool in the eval/observability space — Promptfoo, Braintrust, DeepEval, Langfuse — answers "did my AI system answer correctly?" reprompt answers "am I asking well?" This is an unoccupied category.

---

## Current State (v1.0.0) — Production Stable

### Adapters (8)
Claude Code · OpenClaw · Cursor IDE · Aider · Gemini CLI · Cline · ChatGPT · Claude.ai

### Commands (23)
`scan` · `import` · `report` · `library` · `trends` · `recommend` · `effectiveness` · `merge-view` · `save` · `templates` · `use` · `lint` · `search` · `demo` · `status` · `purge` · `install-hook` · `install-extension` · `extension-status` · `score` · `compare` · `insights` · `digest` · `style` · `wrapped` · `telemetry` · `mcp-serve`

### Integrations
- MCP server (`reprompt mcp-serve`) for IDE integration
- GitHub Action (`action.yml`) for CI prompt quality checks
- HTML dashboard (`reprompt report --html`)
- Browser extension (Chrome/Firefox) via Native Messaging bridge
- JSON output on all commands for pipeline integration

### v1.0.0 Hardening (this release)
- Empty-state UX guidance for `report` and `digest`
- Scan "Try next" onboarding hints for new users
- Feature extraction errors logged (no more silent swallowing)
- DB schema versioning via `PRAGMA user_version`
- CI: ≥90% coverage gate, pre-publish test step
- Stable public API (`score_prompt`, `compare_prompts`, `extract_features`)
- 935+ tests, ≥90% coverage

---

## v1.1+ — Future Work

| Feature | Description |
|---------|-------------|
| `reprompt consolidate` | Automated prompt merging (currently read-only `merge-view` is sufficient) |
| Homebrew formula | `brew install reprompt` via `homebrew-reprompt` tap |
| SSE transport for MCP | Alternative to stdio for remote IDE setups |
| More adapters | Perplexity, Mistral, Grok, Gemini Takeout |
| `reprompt suggest` | Ollama-powered prompt improvement suggestions |
| `.repromptignore` | Per-project filtering rules |
| Team features | Anonymized pattern sharing, CI lint standards |
| Windows Native Messaging | Extension support on Windows |

Nothing beyond v1.1 is formally scheduled.

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
