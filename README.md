# reprompt

[![CI](https://github.com/reprompt-dev/reprompt/actions/workflows/ci.yml/badge.svg)](https://github.com/reprompt-dev/reprompt/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![Python](https://img.shields.io/pypi/pyversions/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Discover, analyze, and evolve your best prompts from AI coding sessions.

*repomix packs your code for AI. reprompt extracts insights from AI.*

Every developer's AI session history contains reusable prompt patterns -- scattered across hundreds of session files. **reprompt** extracts them, deduplicates, analyzes frequency, builds a personal prompt library, and shows you a weekly digest of how your prompting habits are changing over time.

![reprompt demo](docs/launch/demo.gif)

## Quick Start

```bash
pipx install reprompt-cli
reprompt scan
reprompt report
reprompt library

# Weekly digest — compare this week vs last week
reprompt digest

# Try it without any session history
reprompt demo
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

- **Auto-detection** -- finds Claude Code, Cursor, Aider, Gemini CLI, Cline, and OpenClaw sessions automatically
- **Two-layer dedup** -- SHA-256 exact + TF-IDF semantic similarity
- **Hot terms analysis** -- TF-IDF discovers your most-used technical terms
- **K-means clustering** -- groups similar prompts into themes
- **Prompt library** -- extracts high-frequency patterns, auto-categorizes into 12 categories (debug/implement/test/review/refactor/explain/config/document/run/query/generate/plan) with Chinese language support
- **Weekly digest** -- `reprompt digest` compares this week vs last week: prompt volume, specificity trend, category shifts
- **Prompt Science Engine** -- research-backed scoring (`reprompt score`), side-by-side comparison (`reprompt compare`), personal insights (`reprompt insights`)
- **Rich reports** -- beautiful terminal output with tables and bar charts
- **HTML dashboard** -- `reprompt report --html` renders an interactive Chart.js dashboard
- **Multiple formats** -- terminal, JSON (for pipelines), Markdown (for docs)
- **Pluggable adapters** -- add support for any AI coding tool
- **Prompt search** -- find past prompts by keyword across all sessions
- **Zero config** -- works out of the box, customize via env vars or TOML
- **Demo mode** -- `reprompt demo` shows a full report with built-in sample data
- **Prompt recommendations** -- `reprompt recommend` suggests better prompts based on your history and effectiveness

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
| Claude Code | ✅ Supported | `~/.claude/projects/` |
| Cursor | ✅ Supported | `~/Library/Application Support/Cursor/User/` (macOS) |
| Aider | ✅ Supported | `.aider.chat.history.md` |
| Gemini CLI | ✅ Supported | `~/.gemini/tmp/` |
| Cline (VS Code) | ✅ Supported | `globalStorage/saoudrizwan.claude-dev/` |
| OpenClaw / OpenCode | ✅ Supported | `~/.openclaw/` + `~/.opencode/sessions/` |
| Continue.dev | Via MCP | MCP protocol |
| Zed | Via MCP | MCP protocol |
| Codex CLI | Planned | `~/.codex/` |

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

# Search your prompt history
reprompt search "authentication"
reprompt search "debug" --limit 5

# View your prompt library
reprompt library

# Filter by category
reprompt library --category debug

# Export prompt library as Markdown
reprompt library prompts.md

# Get prompt improvement suggestions
reprompt recommend

# Weekly digest — compare this week vs last week
reprompt digest
reprompt digest --period 30d
reprompt digest --quiet          # one-line summary (great for hooks/cron)
reprompt digest --format json

# Prompt Science Engine
reprompt score "your prompt here"
reprompt compare "prompt A" "prompt B"
reprompt insights

# HTML dashboard
reprompt report --html

# Database stats
reprompt status

# Auto-scan after sessions (--with-digest also runs digest summary)
reprompt install-hook
reprompt install-hook --with-digest

# Cleanup old data
reprompt purge --older-than 90d
```

## MCP Server (Claude Code / Continue.dev / Zed)

reprompt includes an MCP server that exposes your prompt analytics as tools for AI coding assistants.

```bash
pip install reprompt-cli[mcp]

# Start the server
reprompt mcp-serve
```

**Register in Claude Code** — add to `.mcp.json` at project root:
```json
{
  "mcpServers": {
    "reprompt": {
      "type": "stdio",
      "command": "reprompt",
      "args": ["mcp-serve"]
    }
  }
}
```

**Available tools:** `search_prompts`, `get_prompt_library`, `get_best_prompts`, `get_trends`, `get_status`, `scan_sessions`

**Available resources:** `reprompt://status`, `reprompt://library`

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

## Troubleshooting

### NumPy conflict in Anaconda environments

If you see an error like:
```
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x
```

This happens when Anaconda's base environment has packages compiled against NumPy 1.x but a newer NumPy 2.x is installed. **This is not a reprompt bug** — it's an environment conflict.

**Fix:** Install reprompt in an isolated environment using pipx:

```bash
pip3 install --user pipx
pipx install reprompt-cli
reprompt scan
```

pipx creates a dedicated virtualenv for reprompt, avoiding conflicts with your system Python or Anaconda.

## Roadmap

- **Prompt version control** — track how your prompts evolve across iterations, with semantic diffing and per-version effectiveness scoring
- **More adapters** — Codex CLI
- **Team analytics** — aggregate insights across team members (opt-in, anonymized)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
