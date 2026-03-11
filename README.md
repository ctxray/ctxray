# reprompt

[![CI](https://github.com/reprompt-dev/reprompt/actions/workflows/ci.yml/badge.svg)](https://github.com/reprompt-dev/reprompt/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![Python](https://img.shields.io/pypi/pyversions/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Discover, analyze, and evolve your best prompts from AI coding sessions.

*repomix packs your code for AI. reprompt extracts insights from AI.*

Every developer's AI session history contains reusable prompt patterns -- scattered across hundreds of session files. **reprompt** extracts them, deduplicates, analyzes frequency, and builds a personal prompt library that evolves over time.

## Quick Start

```bash
pipx install reprompt-cli
reprompt scan
reprompt report
reprompt library
```

## Terminal Report

```
reprompt -- AI Session Analytics
========================================

 Overview
 Total prompts:        1,247
 Unique (deduped):       832
 Sessions scanned:       156
 Sources: claude-code, openclaw

 Top Prompt Patterns
 #  | Pattern                  | Count | Category
 1  | fix the failing test...  |    42 | debug
 2  | add unit tests for...    |    38 | test
 3  | refactor X to use...     |    27 | refactor
```

## Features

- **Auto-detection** -- finds Claude Code and OpenClaw sessions automatically
- **Two-layer dedup** -- SHA-256 exact + TF-IDF semantic similarity
- **Hot terms analysis** -- TF-IDF discovers your most-used technical terms
- **K-means clustering** -- groups similar prompts into themes
- **Prompt library** -- extracts high-frequency patterns, auto-categorizes (debug/implement/test/review/refactor/explain/config)
- **Rich reports** -- beautiful terminal output with tables and bar charts
- **Multiple formats** -- terminal, JSON (for pipelines), Markdown (for docs)
- **Pluggable adapters** -- add support for any AI coding tool
- **Zero config** -- works out of the box, customize via env vars or TOML

## How reprompt Compares

| Feature | reprompt | prompt-manager | agent-sessions | cclog |
|---------|----------|---------------|----------------|-------|
| Multi-tool support | ✅ Claude, OpenClaw, + adapters | ✅ Multiple | ✅ Multiple | ❌ Claude only |
| Exact dedup (SHA-256) | ✅ | ❌ | ❌ | ❌ |
| Semantic dedup (TF-IDF) | ✅ | ❌ | ❌ | ❌ |
| Hot terms analysis | ✅ TF-IDF | ❌ | ❌ | ❌ |
| K-means clustering | ✅ | ❌ | ❌ | ❌ |
| Pattern library | ✅ Auto-categorized | ❌ | ❌ | ❌ |
| CLI interface | ✅ | ✅ TUI | ❌ macOS app | ✅ |
| JSON/Markdown export | ✅ | ❌ | ❌ | ❌ |
| Pluggable adapters | ✅ | ✅ | ❌ | ❌ |
| Zero config | ✅ | ✅ | ✅ | ✅ |

## Supported AI Tools

| Tool | Status | Session Path |
|------|--------|-------------|
| Claude Code | Supported | `~/.claude/projects/` |
| OpenClaw / OpenCode | Supported | `~/.opencode/sessions/` |
| Cursor | Planned | -- |
| Aider | Planned | -- |
| Codex CLI | Planned | -- |
| Gemini CLI | Planned | -- |

## Usage

```bash
# Scan all detected AI tools
reprompt scan

# Scan specific source
reprompt scan --source claude-code

# Scan custom path
reprompt scan --path ~/custom/sessions

# Rich terminal report
reprompt report

# JSON output (for CI/pipelines)
reprompt report --format json

# View your prompt library
reprompt library

# Filter by category
reprompt library --category debug

# Export prompt library as Markdown
reprompt library prompts.md

# Database stats
reprompt status

# Auto-scan after sessions
reprompt install-hook

# Cleanup old data
reprompt purge --older-than 90d
```

## Configuration

Zero config by default. Customize with environment variables or TOML:

```bash
# Environment variables (prefix: REPROMPT_)
REPROMPT_EMBEDDING_BACKEND=ollama reprompt scan
REPROMPT_DB_PATH=~/custom/reprompt.db reprompt status
```

```toml
# ~/.config/reprompt/config.toml
[embedding]
backend = "tfidf"  # tfidf | ollama | local | openai

[storage]
db_path = "~/.local/share/reprompt/reprompt.db"

[dedup]
semantic_threshold = 0.85

[library]
min_frequency = 3
```

## Optional Backends

```bash
pip install reprompt-cli[ollama]   # Ollama API embeddings
pip install reprompt-cli[local]    # sentence-transformers (CPU)
pip install reprompt-cli[openai]   # OpenAI API embeddings
```

## Adding an Adapter

Create a new adapter by subclassing `BaseAdapter`:

```python
from reprompt.adapters.base import BaseAdapter
from reprompt.core.models import Prompt

class MyToolAdapter(BaseAdapter):
    name = "my-tool"
    default_session_path = "~/.my-tool/sessions"

    def parse_session(self, path):
        # Parse session file -> list[Prompt]
        ...

    def detect_installed(self):
        return Path(self.default_session_path).expanduser().exists()
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
