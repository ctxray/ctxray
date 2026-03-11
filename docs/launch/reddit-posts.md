# Reddit Posts

## r/ClaudeAI

**Title:** I built an open-source tool that analyzes your Claude Code session history — found 32% of my prompts were duplicates

**Body:**

I've been using Claude Code daily for months and noticed I kept asking the same things — "fix the failing test," "add unit tests for X," "refactor Y to use Z." So I built **reprompt** to actually quantify this.

**What it does:**
- Scans your `~/.claude/projects/` session files
- Two-layer deduplication: SHA-256 exact match + TF-IDF cosine similarity (catches "fix the auth bug" ≈ "fix the authentication issue")
- Extracts high-frequency prompt patterns and auto-categorizes them (debug/implement/test/review/refactor)
- TF-IDF hot phrases — discovers your most-used technical bigrams/trigrams
- K-means clustering groups similar prompts into themes
- Tracks how your prompting evolves over time (specificity score, vocabulary breadth)
- MCP server so Claude Code can query your prompt library mid-session

**Quick start:**
```bash
pipx install reprompt-cli
reprompt scan
reprompt report
```

**The insight that changed my workflow:** seeing which prompt *patterns* led to productive sessions vs. which ones led to debugging spirals. My "debug" prompts were 3x shorter than my "implement" prompts — and significantly less effective.

Also supports OpenClaw/OpenCode sessions, with Codex CLI and Aider planned.

MIT licensed, ~260 tests, strict mypy. Would love feedback.

GitHub: https://github.com/reprompt-dev/reprompt

---

## r/programming

**Title:** reprompt — CLI tool that extracts and deduplicates prompts from AI coding sessions using TF-IDF + SHA-256

**Body:**

Every AI coding session generates prompts that could be reused — but they're buried in hundreds of session files. I built `reprompt` to extract, deduplicate, and analyze them.

**Technical approach:**
- **Two-layer dedup:** SHA-256 for exact matches, TF-IDF cosine similarity (threshold 0.85) for semantic near-duplicates
- **N-gram analysis:** TF-IDF with bigram/trigram extraction to surface meaningful phrases, not just single words
- **K-means clustering:** Groups similar prompts into discoverable themes
- **Pattern library:** Auto-categorizes extracted patterns (debug/implement/test/review/refactor/explain/config) using keyword heuristics
- **Trend tracking:** Specificity scoring (length × vocabulary breadth × category entropy) over sliding time windows

**Architecture:**
- Python, scikit-learn for ML, SQLite for storage
- Pluggable adapter system — currently Claude Code (JSONL) and OpenClaw (JSON), easy to add new tools
- MCP server for integration with AI coding assistants
- Zero config defaults, optional TOML/env var customization

```bash
pipx install reprompt-cli
reprompt scan          # auto-detects session files
reprompt report        # rich terminal report
reprompt trends        # prompt evolution over time
reprompt effectiveness # session quality scoring
```

When I ran it on my own sessions: 32% near-duplicates, debug prompts 3x shorter than implement prompts, and I naturally started writing more specific prompts after a week of tracking.

MIT, ~260 tests, strict mypy, Python 3.10+.

https://github.com/reprompt-dev/reprompt

---

## r/LocalLLaMA

**Title:** reprompt — analyze your AI coding prompts with TF-IDF dedup, supports Ollama embeddings for local-only semantic search

**Body:**

Built an open-source CLI that extracts and analyzes prompts from AI coding sessions. Thought this community would appreciate the local-first approach.

**Local embedding options:**
- Default: TF-IDF (scikit-learn, zero config, no external calls)
- `pip install reprompt-cli[ollama]` — use your local Ollama instance for embeddings
- `pip install reprompt-cli[local]` — sentence-transformers (CPU)
- `pip install reprompt-cli[openai]` — OpenAI API (if you want)

**What it does:**
- Scans AI coding session files (Claude Code, OpenClaw, more planned)
- SHA-256 exact dedup + semantic dedup via cosine similarity
- TF-IDF hot phrases (bigrams/trigrams, stopword filtered)
- K-means clustering for prompt themes
- Auto-categorized prompt pattern library
- Trend tracking: how your prompting evolves over time
- Session effectiveness scoring

Everything runs locally. No data leaves your machine (unless you explicitly choose OpenAI embeddings).

```bash
pipx install reprompt-cli
reprompt scan && reprompt report
```

Ollama config:
```toml
# ~/.config/reprompt/config.toml
[embedding]
backend = "ollama"
```

Found that 32% of my prompts were near-duplicates. The pattern library is actually useful — I now have a curated set of prompts I know work well for different task types.

MIT licensed. https://github.com/reprompt-dev/reprompt
