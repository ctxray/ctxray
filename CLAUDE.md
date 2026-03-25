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
├── cli.py              # Typer CLI (scan, import, report, search, demo, status, purge, install-hook, install-extension, extension-status, score, compare, insights, digest, style, template [save|list|use], privacy, compress, distill, lint, wrapped, telemetry, mcp-serve) + bare `reprompt` dashboard + plugin loading
├── config.py           # pydantic-settings, env vars (REPROMPT_ prefix) + TOML config
├── demo.py             # Built-in demo data generator (no network required)
├── core/
│   ├── models.py       # Prompt dataclass (auto SHA-256 hash)
│   ├── dedup.py        # Two-layer dedup: exact hash + TF-IDF cosine
│   ├── analyzer.py     # TF-IDF hot terms + K-means clustering
│   ├── library.py      # Pattern extraction + keyword categorization
│   ├── recommend.py    # Prompt recommendations based on history + effectiveness
│   ├── pipeline.py     # Orchestrator: scan → dedup → store → analyze → cluster
│   ├── prompt_dna.py    # PromptDNA dataclass (30+ features per prompt)
│   ├── extractors.py    # Tier 1 feature extraction (regex, <1ms)
│   ├── scorer.py        # Research-calibrated scoring (0-100)
│   ├── segmenter.py     # Three-pass prompt segmentation
│   ├── insights.py      # Personal insights vs research-optimal
│   ├── digest.py        # Two-window comparison for weekly digest
│   ├── style.py         # Personal prompting style fingerprint
│   ├── lang_detect.py   # Language detection (zh/ja/ko/en) via Unicode ranges
│   ├── extractors_zh.py # Chinese feature extraction (jieba + Chinese regex)
│   ├── persona.py       # 6 prompt personas (Architect/Debugger/Explorer/Novelist/Sniper/Teacher)
│   ├── wrapped.py       # WrappedReport dataclass + build_wrapped(db) aggregation
│   ├── privacy.py       # Privacy metadata registry + exposure summary per adapter
│   ├── compress.py      # 4-layer prompt compression (char norm + phrase simplify + filler delete + structure cleanup)
│   ├── suggestions.py   # Command journey suggestions ("→ Try:" hints for 5 core commands)
│   ├── conversation.py  # ConversationTurn, Conversation, DistillResult dataclasses
│   └── distill.py       # 6-signal importance scoring + filtering + summary generation
├── adapters/
│   ├── base.py         # BaseAdapter ABC + parse_conversation() default
│   ├── claude_code.py  # Claude Code JSONL parser
│   ├── openclaw.py     # OpenClaw JSON parser (supports ~/.openclaw/ + legacy ~/.opencode/)
│   ├── cursor.py       # Cursor IDE .vscdb parser (cursorDiskKV + legacy ItemTable)
│   ├── aider.py        # Aider markdown chat history parser (.aider.chat.history.md)
│   ├── gemini.py       # Gemini CLI JSON session parser (~/.gemini/tmp/)
│   ├── cline.py        # Cline VS Code agent task parser (globalStorage/saoudrizwan.claude-dev/)
│   ├── chatgpt.py      # ChatGPT conversations.json export parser
│   └── claude_chat.py  # Claude.ai web chat export parser (JSON/ZIP)
├── embeddings/
│   ├── base.py         # BaseEmbedder ABC
│   ├── tfidf.py        # Default (sklearn, zero config)
│   ├── ollama.py       # Optional: pip install reprompt-cli[ollama]
│   ├── local_embed.py  # Optional: pip install reprompt-cli[local] (sentence-transformers)
│   └── openai_embed.py # Optional: pip install reprompt-cli[openai]
├── bridge/
│   ├── protocol.py    # Native Messaging stdio protocol (4-byte length-prefixed JSON)
│   ├── handler.py     # Message handler (ping, sync_prompts, get_status)
│   ├── host.py        # Entry point launched by Chrome/Firefox as subprocess
│   └── manifest.py    # Manifest generator for Chrome/Firefox/Chromium
├── commands/
│   ├── wrapped.py     # `reprompt wrapped` CLI command (--json, --html, --share)
│   └── telemetry.py   # `reprompt telemetry on|off|status` subcommands
├── telemetry/
│   ├── consent.py     # TelemetryConsent enum, install_id, TOML persistence
│   ├── events.py      # Pydantic TelemetryEvent model, bucketing helpers
│   ├── queue.py       # SQLite telemetry_queue CRUD with 30-day TTL
│   ├── sender.py      # HTTP batch sender (urllib, 2s timeout, fire-and-forget)
│   ├── collector.py   # Orchestrator: consent → event → queue → sender
│   └── prompt.py      # First-run consent prompt (Rich)
├── sharing/
│   ├── client.py      # HMAC-SHA256 signed upload to getreprompt.dev/api/share
│   └── clipboard.py   # Cross-platform clipboard copy (pbcopy/xclip/xsel)
├── storage/
│   └── db.py           # SQLite: prompts, processed_sessions, prompt_patterns, term_stats
└── output/
    ├── terminal.py         # Rich tables + bar charts + hot terms + clusters
    ├── json_out.py         # JSON for pipelines
    ├── markdown.py         # Markdown export
    ├── wrapped_terminal.py # Rich Prompt Wrapped report rendering
    ├── wrapped_html.py     # Self-contained HTML share card (dark theme)
    ├── compress_terminal.py # Rich output for compress command
    └── distill_terminal.py  # Rich output for distill command
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

## Open-Core Architecture (Three Repos)

```
reprompt (public)              ← THIS REPO: open-source CLI core, PyPI: reprompt-cli
reprompt-pro (private)         ← Commercial plugin: persona, wrapped, telemetry
reprompt-extension (private)   ← Browser extension: Chrome/Firefox prompt capture
```

- Plugin system: `cli.py` loads `entry_points(group="reprompt.plugins")` at startup
- reprompt-pro registers via `[project.entry-points."reprompt.plugins"]` in its pyproject.toml
- To enable pro features: `cd ~/projects/reprompt && uv pip install -e ../reprompt-pro`
- Extension connects via Native Messaging bridge (`bridge/` module)
- **Rule:** Commercial code never enters this repo. Pro features go to reprompt-pro.

## Key Conventions

- Package name: `reprompt-cli` (PyPI), CLI command: `reprompt`
- Python >=3.10, type hints required, mypy strict
- ruff for lint + format (line-length=100)
- All db methods use try/finally for conn.close()
- Pattern upsert (not clear+re-insert) for stable IDs
- Prompts starting with `<` are filtered (system-injected XML)
- Config: env vars (REPROMPT_ prefix) > TOML (~/.config/reprompt/config.toml) > defaults
- Tests: pytest, 1397 tests, 95% coverage target

## Prompt Science Engine

Research-backed prompt analysis (added v0.6.0):
- `reprompt score "prompt"` — instant 0-100 scoring with breakdown
- `reprompt compare "a" "b"` — side-by-side feature comparison
- `reprompt insights` — personal patterns vs research-optimal

Papers: Google 2512.14982 (repetition), Stanford 2307.03172 (position),
SPELL EMNLP 2023 (perplexity), Prompt Report 2406.06608 (taxonomy).

## Prompt Compression Engine

Rule-based prompt optimization (added v1.2.0):
- `reprompt compress "prompt"` — 4-layer compression with token savings display
  - Layer 0: Character normalization (curly quotes, zero-width chars, NFKC)
  - Layer 2: Phrase simplification (40+ zh, 50+ en rules)
  - Layer 1: Filler word deletion (50+ zh, 40+ en phrases, jieba-aware)
  - Layer 3: Structure cleanup (markdown strip, emoji, LLM output artifacts)
- `--json` for pipeline integration, `--copy` to clipboard
- `compressibility` field in PromptDNA, visible in insights + HTML dashboard

Sources: LLMLingua (Microsoft), CompactPrompt, TSC, stopwords-iso/zh, Prompt Report 2406.06608.

## Conversation Distillation Engine

Conversation-level analysis (added v1.3.0):
- `reprompt distill` — extract important turns from AI conversations
  - 6-signal importance scoring: position, length, tool_trigger, error_recovery, semantic_shift, uniqueness
  - Hybrid data source: raw session files (full conversation) + DB enrichment
  - `parse_conversation()` on adapters returns both user and assistant turns
  - Claude Code and ChatGPT adapters have full implementations; others fall back to user-only
- `--last N` for recent sessions, `--summary` for compressed output, `--json`, `--copy`
- `--threshold` to control importance cutoff (default 0.3)
- Pro plugin interface: `reprompt.distill_backends` entry point for LLM summarization (future)
