# Changelog

All notable changes to this project will be documented in this file.

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
