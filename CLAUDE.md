# reprompt

CLI tool that extracts, deduplicates, and analyzes prompts from AI coding sessions.

## Build & Test

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest tests/ -v                    # run tests
uv run pytest tests/ -v --cov=reprompt     # with coverage
uv run ruff check src/ tests/              # lint
uv run ruff format src/ tests/             # format
uv run mypy src/reprompt/                  # type check (strict)
uv run python -m build                     # build wheel
```

## Architecture

```
src/reprompt/
├── cli.py              # Typer CLI (scan, report, search, library, demo, status, purge, install-hook)
├── config.py           # pydantic-settings, env vars (REPROMPT_ prefix) + TOML config
├── demo.py             # Built-in demo data generator (no network required)
├── core/
│   ├── models.py       # Prompt dataclass (auto SHA-256 hash)
│   ├── dedup.py        # Two-layer dedup: exact hash + TF-IDF cosine
│   ├── analyzer.py     # TF-IDF hot terms + K-means clustering
│   ├── library.py      # Pattern extraction + keyword categorization
│   └── pipeline.py     # Orchestrator: scan → dedup → store → analyze → cluster
├── adapters/
│   ├── base.py         # BaseAdapter ABC
│   ├── claude_code.py  # Claude Code JSONL parser
│   └── openclaw.py     # OpenClaw JSON parser (supports ~/.openclaw/ + legacy ~/.opencode/)
├── embeddings/
│   ├── base.py         # BaseEmbedder ABC
│   ├── tfidf.py        # Default (sklearn, zero config)
│   ├── ollama.py       # Optional: pip install reprompt-cli[ollama]
│   ├── local_embed.py  # Optional: pip install reprompt-cli[local] (sentence-transformers)
│   └── openai_embed.py # Optional: pip install reprompt-cli[openai]
├── storage/
│   └── db.py           # SQLite: prompts, processed_sessions, prompt_patterns, term_stats
└── output/
    ├── terminal.py     # Rich tables + bar charts + hot terms + clusters
    ├── json_out.py     # JSON for pipelines
    └── markdown.py     # Markdown export
```

## Data Flow

```
Session files → Adapter.parse() → list[Prompt]
  → DedupEngine: SHA-256 exact → TF-IDF cosine similarity
  → SQLite: insert unique prompts, mark dupes
  → Analyzer: TF-IDF hot terms + K-means clusters
  → Library: extract high-frequency patterns, auto-categorize
  → Output: terminal / JSON / Markdown
```

## Key Conventions

- Package name: `reprompt-cli` (PyPI), CLI command: `reprompt`
- Python >=3.10, type hints required, mypy strict
- ruff for lint + format (line-length=100)
- All db methods use try/finally for conn.close()
- Pattern upsert (not clear+re-insert) for stable IDs
- Prompts starting with `<` are filtered (system-injected XML)
- Config: env vars (REPROMPT_ prefix) > TOML (~/.config/reprompt/config.toml) > defaults
- Tests: pytest, 261 tests, 95% coverage target
