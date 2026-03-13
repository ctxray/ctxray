# reprompt Roadmap

> Last updated: 2026-03-12 · Current version: v0.8.2

## Vision

reprompt is the **prompt analytics** tool for AI sessions — understand your patterns, improve your prompting, track your progress. Zero-config, privacy-first, CLI-first.

**Category definition:** reprompt analyzes *human inputs* (how you prompt), not *LLM outputs* (how models respond). Every other tool in the eval/observability space — Promptfoo, Braintrust, DeepEval, Langfuse — answers "did my AI system answer correctly?" reprompt answers "am I asking well?" This is an unoccupied category.

---

## Current State (v0.8.2)

### Adapters (6)
Claude Code · OpenClaw · Cursor IDE · Aider · Gemini CLI · Cline

### Commands
`scan` · `report` · `library` · `trends` · `recommend` · `effectiveness` · `merge-view` · `save` · `templates` · `lint` · `search` · `demo` · `status` · `purge` · `install-hook` · `score` · `compare` · `insights` · `digest` · `mcp-serve`

### Integrations
- MCP server (`reprompt mcp-serve`) for IDE integration
- GitHub Action (`action.yml`) for CI prompt quality checks
- HTML dashboard (`reprompt report --html`)
- JSON output on all commands for pipeline integration

---

## v0.9 — Chat AI Sources

**Theme:** Bring web-based AI chat data into reprompt analysis.

### New Adapters
| Tool | Mechanism | Status |
|------|-----------|--------|
| ChatGPT | `conversations.json` from OpenAI data export | Planned |
| Claude.ai | ZIP export from Account settings | Planned |
| Gemini Takeout | Google Takeout → Gemini Apps Activity JSON | Planned |

### New Command: `reprompt import`
```bash
reprompt import conversations.json            # auto-detect source
reprompt import export.zip --source claude-chat
reprompt import takeout.json --source gemini-takeout
```
`reprompt scan` = auto-discover session directories. `reprompt import` = explicit file from a manual export. Both write to the same SQLite DB; all existing commands (`report`, `digest`, `trends`) work with imported data.

### CLI Improvements
- **Template variables:** `reprompt use <name> key=value` with `{placeholder}` substitution
- **`reprompt style`:** Personal prompting style fingerprint (avg length, categories, opening patterns)
- **Configurable lint:** `.reprompt.yml` for per-project rule customization

### Category Expansion
New categories for chat prompts: `research` · `creative` · `summarize` · `translate` · `draft` · `analyze` · `plan`

---

## v1.0 — Browser Extension

**Theme:** Real-time capture from any web-based AI tool, bridged to reprompt analysis.

### reprompt-extension (separate repo)
A companion browser extension that captures prompts from web AI tools and pipes them into reprompt for analysis.

**Supported platforms (priority order):**
1. Gemini — biggest pain point (tab-close deletes history, Activities-off blocks cross-device)
2. ChatGPT — largest user base
3. Claude.ai — core audience overlap
4. Perplexity, Mistral, Grok (v1.1+)

**Architecture:**
- Service Worker intercepts API requests (not DOM scraping — survives UI changes)
- 100% local storage (IndexedDB) — zero server, zero telemetry
- Syncs to reprompt CLI via [Chrome Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
- `reprompt install-extension` registers the native messaging host
- macOS + Linux supported at v1.0; Windows deferred to v1.1

**Privacy guarantees:**
- No network requests except to AI platforms you're already using
- Explicit prompt list visible in extension popup
- Per-domain opt-out controls
- Full delete/export from popup

### New CLI Commands
```bash
reprompt install-extension   # register native messaging host
reprompt extension status    # show connection status + pending sync count
```

---

## Post-v1.0

v1.1 will likely include Windows Native Messaging support, more platforms (Perplexity, Mistral, Grok), `reprompt suggest` (opt-in Ollama integration: given a prompt draft, suggest improvements using your personal history as few-shot examples), and `.repromptignore` filtering. Team features (anonymized pattern sharing, CI lint standards) are candidates for v1.2. Nothing beyond v1.1 is formally scheduled.

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
- **Browser extension** — see `reprompt-extension` repo (coming soon)

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.
