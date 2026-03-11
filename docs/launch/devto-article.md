# Dev.to Article

**Title:** I Analyzed 1,200+ AI Coding Prompts and Found 32% Were Duplicates — So I Built a Tool to Fix It

**Tags:** ai, python, productivity, opensource

**Cover image:** [terminal screenshot of reprompt report]

---

Every developer using AI coding tools generates hundreds of prompts per week. They're scattered across session files — never reviewed, never reused, never learned from.

I realized I was asking Claude Code the same things over and over: "fix the failing test," "add unit tests for X," "refactor Y to use Z." So I built [reprompt](https://github.com/reprompt-dev/reprompt) to quantify the pattern.

## What reprompt Does

reprompt scans your AI coding session files, deduplicates them, and surfaces insights about your prompting habits.

```bash
pipx install reprompt-cli
reprompt scan
reprompt report
```

### Two-Layer Deduplication

Most dedup tools use exact matching. But "fix the auth bug" and "fix the authentication issue" are clearly the same intent.

reprompt uses two layers:

1. **SHA-256 hash** — catches exact duplicates instantly
2. **TF-IDF cosine similarity** — catches semantic near-duplicates with a configurable threshold (default 0.85)

This caught 32% of my prompts as near-duplicates.

### Hot Phrases, Not Hot Words

Single-word frequency analysis is noisy — "function," "test," "add" tell you nothing. reprompt uses TF-IDF with bigram/trigram extraction and English stopword filtering to surface meaningful phrases like "failing test fixture" or "refactor authentication middleware."

### Prompt Pattern Library

reprompt extracts high-frequency patterns and auto-categorizes them:

| Category | Example Pattern |
|----------|----------------|
| debug | "fix the failing test..." |
| test | "add unit tests for..." |
| refactor | "refactor X to use..." |
| implement | "add a new endpoint for..." |
| review | "review this code for..." |

Over time, this becomes your personal prompt library — the prompts you know work well for different task types.

### Trend Tracking

`reprompt trends` shows how your prompting evolves:

- **Specificity score** — are your prompts getting more detailed over time?
- **Vocabulary breadth** — are you using more technical terms?
- **Category distribution** — what types of prompts dominate each period?
- **Delta arrows** — visual indicators of improvement or regression

### Session Effectiveness

`reprompt effectiveness` scores each session on:

- Clean exit (no crashes/errors)
- Duration heuristics
- Tool call density
- Error ratio
- Prompt specificity

This helps identify which *types* of sessions are most productive.

### MCP Server

reprompt includes an MCP server that exposes your prompt analytics as tools for AI coding assistants:

```bash
pip install reprompt-cli[mcp]
reprompt mcp-serve
```

Register it in Claude Code's `.mcp.json` and your AI assistant can search your prompt history, suggest better prompts, and learn from your patterns mid-session.

## What Surprised Me

1. **32% duplication rate** — I thought I was being original. I wasn't.
2. **Debug prompts are 3x shorter** than implement prompts — and less effective. Turns out "fix it" is a terrible prompt.
3. **Tracking changes behavior** — after a week of seeing my metrics, I naturally started writing more specific prompts. The specificity score went up 15%.

## Technical Details

- Python 3.10+, scikit-learn for TF-IDF + K-means, SQLite for storage
- ~260 tests, strict mypy, ruff for lint/format
- Pluggable adapter system for different AI tools
- Pluggable embedding backends: TF-IDF (default), Ollama, sentence-transformers, OpenAI
- Zero config defaults, optional TOML/env var customization
- Everything runs locally — no data leaves your machine

## Supported Tools

| Tool | Status |
|------|--------|
| Claude Code | Supported |
| OpenClaw / OpenCode | Supported |
| Codex CLI | Planned |
| Aider | Planned |
| Gemini CLI | Planned |
| Continue.dev / Zed | Via MCP |

## Try It

```bash
pipx install reprompt-cli
reprompt scan
reprompt report
reprompt library
reprompt trends
```

MIT licensed. Contributions welcome.

**GitHub:** https://github.com/reprompt-dev/reprompt
**PyPI:** https://pypi.org/project/reprompt-cli/

---

What metrics would you find useful? What would make you check your prompt analytics daily? I'd love to hear what features would be most valuable to your workflow.
