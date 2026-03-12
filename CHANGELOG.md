# Changelog

All notable changes to this project will be documented in this file.

## [0.7.3] - 2026-03-12

### Improved
- **Smarter prompt clustering** — K-means now runs on LSA-reduced (TruncatedSVD + L2-normalized) TF-IDF vectors instead of raw sparse vectors; eliminates the single-dominant-cluster problem where 95%+ of prompts collapsed into one bucket
- **Auto-select optimal K** — cluster count is now determined automatically via silhouette score sweep (K=3..15) rather than a fixed K=5; pass `--clusters N` to `reprompt report` to override
- **Cleaner Hot Phrases** — shell tool names (`cd`, `uv`, `pytest`, `git`, `bash`, etc.) added to domain stop word list; year-number bigrams (e.g. "2025 2026") filtered from n-gram extraction; n-gram range expanded to (1, 3) to surface meaningful single-word domain signals
- **TF-IDF quality flags** — added `sublinear_tf=True` and `max_df=0.8` to dampen high-frequency noise and auto-remove corpus-ubiquitous terms

## [0.7.2] - 2026-03-12

### Added
- **`skill_invocation` prompt category** — skill/workflow invocations (e.g. `superpowers:brainstorming`, `feature-dev:code-architect`) are now classified as their own category instead of polluting `other` or being silently filtered. Shows up in Prompt Categories so you can see what % of your sessions are workflow-driven vs content-driven
- **`reprompt purge --all`** — wipes the entire database and resets session tracking (useful to remove demo data or start fresh). Follow with `reprompt scan` to reimport

### Fixed
- Skill invocations previously added to filter list (wrong approach) — they are analytically valuable and now correctly categorized instead of discarded
- Regex detection covers any `namespace:skill-name` pattern (9+ char namespace) — future-proof, no hardcoded list required

### Changed
- Tests: 490 → 493

## [0.7.1] - 2026-03-11

### Added
- **12 prompt categories** (was 8) — new: `document`, `run`, `query`, `generate`, `plan`; reduces the "other" bucket from ~56% to an estimated <15%
- **Chinese language support** for all categories — bilingual keyword matching (e.g. "整理" → document, "启动" → run, "是否" → query)
- **Coding domain stop words** for TF-IDF Hot Phrases — ~60 programming-specific terms filtered (generic verbs: write/create/implement; structure nouns: function/class/variable; LeetCode templates: given/input/output). Hot Phrases now surfaces meaningful domain signals instead of generic boilerplate
- **Subagent session labeling** — Claude Code subagent sessions (stored under `{project}/{uuid}/subagents/`) are now correctly attributed to their parent project with a `[subagent]` tag (e.g. `claudeAutomation [subagent]`), instead of all appearing under a mystery "subagents" project

### Fixed
- `cluster_prompts()` previously used no stop words; now uses the same coding stop word list as `compute_tfidf_stats()` for consistent clustering quality
- "write a function…" prompts were falling into `other`; now correctly categorized as `implement`
- `not working`, `exception`, `fail` now correctly trigger the `debug` category

### Changed
- Tests: 478 → 489

## [0.7.0] - 2026-03-11

### Added
- `reprompt digest` — weekly summary comparing current vs previous period: prompt volume, specificity score, avg length, category distribution with direction arrows
- `reprompt digest --quiet` — one-line summary for use in hooks and cron jobs
- `reprompt digest --format json` — machine-readable digest output
- `reprompt digest --period 30d` — configurable comparison window (7d, 14d, 30d)
- `reprompt install-hook --with-digest` — also registers `reprompt digest --quiet` as a Stop hook so every session ends with a summary
- `digest_log` DB table — persists digest history for trend tracking

### Changed
- Tests: 454 → 478

## [0.6.0] - 2026-03-11

### Added
- **Prompt Science Engine** — research-backed prompt analysis
- `reprompt score "prompt"` — instant 0-100 quality score with breakdown (specificity, position bias, repetition, perplexity)
- `reprompt compare "a" "b"` — side-by-side feature comparison of two prompts
- `reprompt insights` — personal patterns vs research-optimal benchmarks, wired into `reprompt scan`
- `PromptDNA` dataclass — 30+ features per prompt extracted at scan time
- Tier 1 feature extractors — regex-based, <1ms per prompt
- Research-calibrated scorer (Google 2512.14982, Stanford 2307.03172, SPELL EMNLP 2023, Prompt Report 2406.06608)
- Three-pass prompt segmenter (Prompt Report taxonomy)
- `prompt_features` DB table for PromptDNA storage

### Changed
- Tests: 371 → 454

## [0.5.0] - 2026-03-11

### Added
- `reprompt lint` — prompt quality linter with GitHub Action integration
- Gemini CLI adapter — parses `~/.gemini/tmp/` session files
- Cline (VS Code) adapter — parses `globalStorage/saoudrizwan.claude-dev/` task files
- Comprehensive prompt filters for all AI coding tools (slash commands, system injections, tool outputs)
- Shared filter module (`adapters/filters.py`) extracted for reuse across all adapters

### Changed
- Tests: 331 → 371

## [0.4.0] - 2026-03-11

### Added
- Cursor IDE adapter — parses `.vscdb` files (Composer `cursorDiskKV` + legacy `ItemTable` schemas)
- Aider adapter — parses `.aider.chat.history.md` chat history files
- HTML dashboard report — `reprompt report --html` renders interactive Chart.js charts
- `reprompt merge-view` — clusters near-duplicate prompts and selects canonical versions
- `reprompt templates` / `reprompt save` — save and reuse prompt templates
- Auto-report after `reprompt scan` (skip with `--quiet`)
- `reprompt install-hook` now prompts if not yet configured

### Changed
- Tests: 256 → 331

## [0.3.2] - 2026-03-11

### Fixed
- Fix ANSI escape code leak in terminal report (double-render through Rich console)
- Filter subagent/automation prompts ("You are implementing Task...", "## Task:", etc.)
- Strip file paths from TF-IDF input to prevent path fragment n-grams
- Filter noise phrases (username/path tokens) from Hot Phrases results

### Added
- `reprompt recommend` command — suggests better prompts based on effectiveness, category balance, and specificity
- `reprompt demo` command — run a full report with built-in sample data, no session history needed
- Cursor IDE adapter — parses `.vscdb` files from both Composer (cursorDiskKV) and legacy (ItemTable) schemas
- `reprompt scan` now auto-shows report after scanning (skip with `--quiet`)
- `reprompt scan` suggests `install-hook` if not yet configured
- Demo data generator script (`scripts/generate_demo_data.py`) using CodeAlpaca-20K
- VHS recording script for terminal demo GIF
- Launch materials (Show HN, Reddit, Twitter, Dev.to, Chinese communities)

## [0.3.1] - 2026-03-11

### Added
- MCP server (`reprompt mcp-serve`) for Claude Code, Continue.dev, and Zed integration
- 6 MCP tools: search_prompts, get_prompt_library, get_best_prompts, get_trends, get_status, scan_sessions
- 2 MCP resources: reprompt://status, reprompt://library
- `fastmcp` optional dependency (`pip install reprompt-cli[mcp]`)
- MCP setup guide in README

### Changed
- Tests: 246 → 256
- Updated supported tools table (Codex CLI, Aider, Gemini CLI, Continue.dev, Zed)

## [0.3.0] - 2026-03-11

### Added
- `reprompt trends` — prompt evolution tracking with specificity scoring, delta arrows, insights
- `reprompt effectiveness` — session quality scoring (clean exit, error ratio, duration heuristics)
- Session metadata extraction during scan (tool calls, errors, duration, final status)
- Hot Phrases: TF-IDF now extracts bigram/trigram phrases instead of single words
- Prompt snapshots table for time-series trend data
- IDE prefix stripping (`<ide_opened_file>`, `<ide_selection>`) — preserves real user questions
- Compact/continuation message filtering (blocks session compaction noise)
- Troubleshooting FAQ in README (Anaconda NumPy conflict)

### Changed
- "Hot Terms" → "Hot Phrases" in terminal report (n-gram based, stopwords filtered)
- Tests: 176 → 246

## [0.2.0] - 2026-03-11

### Added
- `reprompt search <query>` command for keyword search across prompt history
- Local embedding backend (`pip install reprompt-cli[local]`, sentence-transformers)
- OpenAI embedding backend (`pip install reprompt-cli[openai]`)
- TOML config file support (`~/.config/reprompt/config.toml`)
- K-means clustering output in terminal report
- TF-IDF hot terms table in terminal report
- OpenClaw adapter supports new `~/.openclaw/` path (backward compatible)
- Competitive comparison table in README

### Fixed
- `install-hook` now registers in Claude Code `settings.json` (was writing unregistered shell script)
- `ollama_url` config setting now propagates to OllamaEmbedder
- Pattern IDs are stable across report runs (upsert instead of clear+re-insert)
- Text truncation in all outputs now shows `...` suffix
- JSON output uses `print()` instead of Rich `console.print()` to avoid markup corruption

### Changed
- Tests: 118 → 176
- OpenClaw adapter checks both `~/.openclaw/` (new) and `~/.opencode/` (legacy)

## [0.1.1] - 2026-03-10

### Fixed
- Prevent connection leak in all database methods (try/finally)
- Fix session marking for incremental scan accuracy
- Fix purge validation for date format parsing
- Fix pattern dedup to avoid duplicate entries
- Improve Ollama error messages when server is unreachable
- Fix JSON output (`--format json`) producing invalid escape sequences

### Added
- `--version` / `-V` flag to CLI
- mypy strict mode compliance

## [0.1.0] - 2026-03-10

### Added

- Initial release
- Claude Code session adapter (JSONL format)
- OpenClaw session adapter
- Two-layer deduplication (SHA-256 exact + TF-IDF semantic)
- TF-IDF hot terms analysis
- K-means prompt clustering
- Prompt pattern library with auto-categorization
- Rich terminal reports with tables and bar charts
- JSON output for CI/pipeline integration
- Markdown export for prompt library
- `install-hook` command for Claude Code automation
- Ollama embedding backend (optional)
- Zero-config defaults with env var and TOML override
