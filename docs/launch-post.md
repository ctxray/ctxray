# Launch Post Draft

Target: Hacker News (Show HN), Reddit (r/programming, r/MachineLearning), Twitter/X

---

## Show HN: reprompt -- Discover and reuse your best prompts from AI coding sessions

Every developer using AI coding tools has hundreds of session files scattered across their system. Buried in those sessions are the prompts that actually worked -- the ones that led to clean implementations, successful debugging, and productive refactoring.

**reprompt** is a CLI tool that extracts prompts from your AI coding session history, deduplicates them (exact + semantic), analyzes frequency patterns, and builds a personal prompt library that evolves over time.

### What it does

- Scans Claude Code and OpenClaw/OpenCode sessions automatically
- Two-layer dedup: SHA-256 for exact matches, TF-IDF cosine similarity for semantic near-duplicates
- Discovers your "hot terms" via TF-IDF analysis
- K-means clustering groups similar prompts into themes
- Auto-categorizes patterns: debug, implement, test, review, refactor, explain, config
- Exports as terminal report, JSON (for pipelines), or Markdown

### Quick start

```bash
pipx install reprompt-cli
reprompt scan          # finds sessions automatically
reprompt report        # see your patterns
reprompt library       # browse your prompt library
```

### Why I built this

After 6+ months of daily AI-assisted coding, I realized I was re-inventing prompts constantly. The same debugging approach, the same "add tests for X" pattern, the same refactoring instructions -- typed fresh each time.

Session files are write-once logs. They're not designed for retrieval. reprompt turns that dead data into a living library of your best practices.

### Technical details

- Python, MIT licensed, pip-installable
- Zero external dependencies for core (scikit-learn for TF-IDF/clustering, Rich for terminal output)
- Pluggable adapter pattern -- adding a new AI tool is ~30 lines
- Optional embedding backends: Ollama, sentence-transformers, OpenAI
- SQLite storage, zero config defaults

GitHub: https://github.com/reprompt-dev/reprompt
PyPI: https://pypi.org/project/reprompt-cli/

---

## Twitter/X version (thread)

**Tweet 1:**
I built reprompt -- a CLI that mines your AI coding sessions for reusable prompt patterns.

After months of Claude Code, I realized my best prompts were buried in hundreds of JSONL files. Same patterns, retyped from scratch every time.

`pipx install reprompt-cli`

**Tweet 2:**
How it works:
1. Scans your Claude Code / OpenClaw sessions
2. SHA-256 + TF-IDF dedup (exact + semantic)
3. K-means clustering for theme discovery
4. Auto-categorizes: debug, implement, test, review...
5. Builds a prompt library that grows over time

**Tweet 3:**
Three commands to get started:

```
reprompt scan     # auto-detect sessions
reprompt report   # see your patterns
reprompt library  # browse & export
```

Zero config. MIT licensed. Adapter pattern makes adding new AI tools trivial (~30 lines).

GitHub: https://github.com/reprompt-dev/reprompt

---

## Reddit r/programming version

**Title:** reprompt: CLI tool to extract, deduplicate, and analyze prompts from your AI coding sessions

**Body:**

I've been using Claude Code daily for months and noticed I kept writing the same types of prompts over and over. My session history had hundreds of files with reusable patterns buried in them -- but no way to search or learn from them.

So I built **reprompt**, a CLI that:

- Auto-detects Claude Code and OpenClaw session files
- Extracts user prompts and deduplicates them (SHA-256 exact + TF-IDF semantic)
- Runs TF-IDF analysis to find your "hot terms"
- Uses K-means clustering to group similar prompts
- Auto-categorizes patterns into debug/implement/test/review/refactor/explain/config
- Exports as rich terminal report, JSON, or Markdown

It's designed to be extensible -- adding support for a new AI tool is just subclassing `BaseAdapter` and implementing `parse_session()`. Cursor and Codex CLI adapters are planned.

Install: `pipx install reprompt-cli`

- GitHub: https://github.com/reprompt-dev/reprompt
- PyPI: https://pypi.org/project/reprompt-cli/
- License: MIT
- Python 3.10+
