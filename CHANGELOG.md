# Changelog

All notable changes to this project will be documented in this file.

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
