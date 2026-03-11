# Launch Post Draft

Target: Hacker News (Show HN), Reddit (r/programming, r/MachineLearning), Twitter/X

---

## Show HN: reprompt -- Discover and reuse your best prompts from AI coding sessions

Every developer using AI coding tools has hundreds of session files scattered across their system. Buried in those sessions are the prompts that actually worked -- the ones that led to clean implementations, successful debugging, and productive refactoring.

**reprompt** is a CLI tool that extracts prompts from your AI coding session history, deduplicates them (exact + semantic), analyzes frequency patterns, and builds a personal prompt library that evolves over time.

### What it does

- Auto-detects 6 AI coding tools: Claude Code, Cursor IDE, Aider, Gemini CLI, Cline, OpenClaw
- Two-layer dedup: SHA-256 for exact matches, TF-IDF cosine similarity for semantic near-duplicates
- Discovers your "hot terms" via TF-IDF analysis
- K-means clustering groups similar prompts into themes
- Auto-categorizes patterns: debug, implement, test, review, refactor, explain, config
- Session effectiveness scoring (composite: tool calls, errors, specificity)
- Prompt specificity and vocabulary trend tracking over time
- `reprompt lint` — CI-ready prompt quality checks with GitHub Action
- Save and reuse your best prompts as templates
- Exports as terminal report, JSON (for pipelines), Markdown, or HTML dashboard

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
- Pluggable adapter pattern -- adding a new AI tool is ~50 lines
- Optional embedding backends: Ollama, sentence-transformers, OpenAI
- SQLite storage, zero config defaults
- 371 tests, strict mypy, ~4,700 lines

GitHub: https://github.com/reprompt-dev/reprompt
PyPI: https://pypi.org/project/reprompt-cli/

---

## Twitter/X version (thread)

**Tweet 1:**
I built reprompt -- a CLI that analyzes your AI coding prompts across 6 tools (Claude Code, Cursor, Aider, Gemini CLI, Cline, OpenClaw).

TF-IDF dedup, K-means clustering, effectiveness scoring, trend tracking. All local, zero config.

`pipx install reprompt-cli`

**Tweet 2:**
What it does:
1. Auto-detects 6 AI coding tools
2. SHA-256 + TF-IDF dedup (exact + semantic)
3. K-means clustering for theme discovery
4. Auto-categorizes: debug, implement, test, review...
5. Scores session effectiveness
6. Tracks prompting trends over time
7. CI-ready lint with GitHub Action

**Tweet 3:**
Three commands to get started:

```
reprompt scan     # auto-detect sessions
reprompt report   # see your patterns
reprompt library  # browse & export
```

Zero config. MIT licensed. 371 tests. Adding new AI tools is ~50 lines.

GitHub: https://github.com/reprompt-dev/reprompt

---

## Reddit r/programming version

**Title:** reprompt: CLI tool to extract, deduplicate, and analyze prompts from your AI coding sessions

**Body:**

I've been using AI coding tools daily for months and noticed I kept writing the same types of prompts over and over. My session history had hundreds of files with reusable patterns buried in them -- but no way to search or learn from them.

So I built **reprompt**, a CLI that:

- Auto-detects 6 AI coding tools (Claude Code, Cursor, Aider, Gemini CLI, Cline, OpenClaw)
- Extracts user prompts and deduplicates them (SHA-256 exact + TF-IDF semantic)
- Runs TF-IDF analysis to find your "hot terms"
- Uses K-means clustering to group similar prompts
- Auto-categorizes patterns into debug/implement/test/review/refactor/explain/config
- Scores session effectiveness (composite metric)
- Tracks prompt specificity trends over time
- `reprompt lint` for CI-ready prompt quality checks (GitHub Action included)
- Exports as terminal report, JSON, Markdown, or HTML dashboard

Adding support for a new AI tool is ~50 lines. GitHub Copilot Chat, Continue.dev, and Windsurf adapters are planned.

Install: `pipx install reprompt-cli`

- GitHub: https://github.com/reprompt-dev/reprompt
- PyPI: https://pypi.org/project/reprompt-cli/
- License: MIT
- Python 3.10+, 371 tests
