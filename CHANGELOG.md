# Changelog

All notable changes to this project will be documented in this file.

## [2.2.0] - 2026-04-01

### Added
- **Prompt builder** — `reprompt build "task" --file src/auth.ts --error "TypeError" --constraint "keep tests"` assembles well-scored prompts from components. Model-aware formatting: XML tags for Claude, markdown headers for GPT. Shows score, tier, and suggestions for missing components.
- **Unified diagnostic** — `reprompt check "prompt"` runs score + lint + rewrite in one command. Shows dimensional breakdown, strengths, suggestions with point values, lint issues, and auto-rewrite preview.
- **Prompt explainer** — `reprompt explain "prompt"` explains what makes a prompt good or bad in plain English. Educational feedback with research-backed insights per dimension.
- Tests: 1741 → 1846

## [2.1.0] - 2026-04-01

### Added
- **Model-specific lint rules** — `reprompt lint --model claude/gpt/gemini` checks prompts against model-specific best practices. 8 rules: XML tag preference (Claude), markdown structure (GPT), JSON instruction requirements (GPT), CoT anti-pattern for o-series (GPT), prompt length limits (Gemini), broad negative detection (Gemini). Based on official model documentation.
- **Diff preview for rewrite** — `reprompt rewrite --diff` shows a git-style unified diff between original and rewritten prompt. Color-coded: red removals, green additions, cyan range markers.
- **Token budget lint** — `reprompt lint --max-tokens 4096` warns when prompts exceed a token budget. Configurable via `.reprompt.toml` (`max-tokens`) or CLI flag. Uses locale-aware token estimation from cost module.
- Tests: 1716 → 1741

## [2.0.2] - 2026-04-01

### Changed
- **Scoring rebalance** — Structure weight reduced 25→15, Clarity increased 15→25. Plain-text prompts now score 55-65 instead of 35-45. Real-world conversational prompts are no longer penalized for lacking markdown structure.
- **Tier labels** — Scores display as EXPERT (85+), STRONG (70+), GOOD (50+), BASIC (30+), DRAFT (<30) instead of raw numbers. Applied across CLI, extension badge, popup, and HTML dashboard.
- **Positive UX feedback** — Score output now includes "Strengths" section showing what the prompt does well. Suggestions show expected point gain (`+N pts`). Badge color thresholds adjusted: 85/60/40/25.

## [2.0.1] - 2026-03-31

### Added
- **Project-level quality comparison** — `reprompt projects` aggregates session quality, efficiency, focus scores, and frustration signals per project. Supports `--source` filter, `--json`, `--copy`.
- Tests: 1670 → 1716

## [2.0.0] - 2026-03-31

### Changed
- **Major version bump** — the rewrite engine marks the shift from passive analysis (v1.x) to active prompt coaching (v2.0). reprompt now scores, rewrites, and optimizes your AI prompts automatically.

## [1.10.0] - 2026-03-31

### Added
- **Prompt rewrite engine** — `reprompt rewrite "prompt"` applies 4 rule-based transformations: filler removal (reuses compress engine), instruction front-loading (Stanford position bias), key requirement echo (Google repetition research), hedging cleanup (12 regex patterns). Shows before/after score delta and manual suggestions. No LLM needed, under 50ms.
- **`reprompt init` command** — generates `.reprompt.toml` config with all lint rules documented and commented defaults. `--force` to overwrite existing.
- Tests: 1597 → 1670

## [1.9.1] - 2026-03-31

### Added
- **Configurable lint rules** — `.reprompt.toml` or `[tool.reprompt.lint]` in `pyproject.toml`. Supports `score-threshold`, `min-length`, `short-prompt`, `vague-prompt`, `debug-needs-reference`, `file-extensions`. Config walks up from CWD. CLI flags override file config.
- Tests: 1567 → 1597

## [1.9.0] - 2026-03-31

### Added
- **Bidirectional bridge** — Native Messaging `sync_result` now returns insights (avg score, score trend, top coaching tip) back to the browser extension. New `get_insights` message type for full analysis including repetition data and pattern info.
- `get_recent_scores(limit)` DB method for trend computation.
- Tests: 1545 → 1567

## [1.8.1] - 2026-03-31

### Added
- **Cross-session repetition detection** — `reprompt repetition` detects recurring prompts across different AI sessions using TF-IDF + containment clustering (threshold 0.75). Shows repetition rate, recurring topics ranked by session count, and date ranges. Integrated into `reprompt insights` output.
- Tests: 1529 → 1545

## [1.8.0] - 2026-03-31

### Added
- **Session quality metrics** — `reprompt sessions` provides composite 0-100 session scoring combining prompt quality, efficiency, focus, and outcome. Frustration signal detection: abandonment, escalation, stall turns. Rich table and detail views.

### Fixed
- **Pipeline type mismatch** — `parse_conversation()` returns `list[ConversationTurn]`, not `Conversation`. Pipeline now wraps turns correctly. Without this fix, session quality scoring silently failed.
- **Bridge shell injection** — quoted `sys.executable` in bridge wrapper script to prevent command injection when Python path contains spaces.
- **Unclamped scores** — efficiency and focus component scores now clamped to 0-100 range.
- Tests: 1497 → 1529

## [1.7.1] - 2026-03-29

### Added
- **Expanded privacy scanner** — 10 new detection patterns: SSH private keys (RSA/EC/DSA/OPENSSH/PKCS#8), PEM certificates, service tokens (Slack bot/user/app, Google API, npm), database connection strings (PostgreSQL, MySQL, MongoDB, Redis). 28 new tests. Closes #12.

## [1.7.0] - 2026-03-28

### Added
- **GitHub Action PR comments** — `comment-on-pr: true` posts quality report as PR comment with markdown table, collapsible violations, and score summary. Updates existing comment on re-push (no duplicates).
- **Token cost estimation** — `reprompt score` shows ~tokens and $cost. `reprompt insights` shows total prompt cost. `reprompt report` overview includes estimated cost. MCP `score_prompt` includes token count and cost.
- Locale-aware token counting: 1.3x words (EN), 1.5x chars (CJK).
- Price table: Claude Sonnet/Opus/Haiku, GPT-4o/mini, Gemini, DeepSeek. Auto-detect model from adapter source.
- Tests: 1497 → 1529

## [1.6.2] - 2026-03-28

### Fixed
- **Security: shell injection in GitHub Action** — inputs now passed via env vars, not string interpolation.
- **Bridge: 1MB message limit** — enforce Chrome Native Messaging size limit with proper JSON decode error handling.

### Improved
- SQLite WAL mode + 10s timeout for concurrent access safety.
- MCP: all 6 tools wrapped in try/except with structured error responses; `check_privacy` uses SQL LIMIT.
- Dedup: skip O(n²) semantic layer when batch > 5000 prompts.
- ChatGPT adapter: warn on files > 200MB.
- First-run dashboard shows "Found N sessions (~M turns) across K tools".
- `purge --all` now requires confirmation.
- MCP server consolidated from 10 to 6 focused tools.

## [1.6.1] - 2026-03-28

### Fixed
- **Critical: `reprompt scan` crash** — `compute_pattern_effectiveness` failed on prompts containing SQL LIKE wildcards (`%`, `_`). Replaced `LIKE` with `INSTR()` for exact substring matching.
- **Score calibration** — single-paragraph prompts incorrectly received 0/20 for Position (instruction was treated as "buried in the middle"). Now correctly scores instruction-at-start as optimal position.
- **Compress grammar bugs** — fixed leading whitespace after filler deletion, dangling "that" after "the thing is" removal, orphaned commas, and remnant pleasantry fragments.
- **Deprecated command references** — `reprompt library` and `reprompt trends` references in report footer and scan guidance now point to `reprompt template list` and `reprompt digest --trends`.
- **Wrong adapter names** — `--source` help examples used non-existent `chatgpt-ext`; fixed to `chatgpt-export`.

### Improved
- **Compress engine** — added 15 filler phrases (`kind of`, `sort of`, `additionally`, `the fact that`, etc.) and 16 phrase simplification rules (`take a look at` → `check`, `let me know` → removed, etc.). Added post-compression cleanup pass for whitespace, punctuation, and sentence capitalization. Typical savings improved from 3-33% to 38-60%.
- **Score UX** — suggestions now sorted by impact (high first); paper citations dimmed; new "Very Poor" grade tier for scores under 20.
- **CLI help** — added usage examples to 7 key commands (score, scan, compress, compare, distill, lint, privacy). Added Quick Start guide to main `--help`. Standardized `--source` option across all commands with `-s` shorthand.
- **Help panels** — moved `digest` from Manage to Analyze panel. Listed all 9 adapters in `scan --help`.
- Tests: 1490 → 1497

## [1.6.0] - 2026-03-28

### Added
- **Agent workflow analysis** — `reprompt agent` detects error loops, tool call patterns, and session efficiency from existing session files. Zero config, zero instrumentation.
- **Codex CLI adapter** — full support for OpenAI Codex CLI sessions (`~/.codex/sessions/`), including user/assistant turns, tool calls (shell + function), error detection with exit codes, and file path tracking. 9th adapter.
- **Sensitive content detection** — `reprompt privacy --deep` scans stored prompts for API keys, JWT tokens, emails, IP addresses, passwords, env secrets, and home paths. All regex-based, zero network.
- **Chrome Web Store extension** — `install-extension` now defaults to the published extension ID; `extension-status` shows the Chrome Web Store install link.
- **Extension E2E tests** — 8 tests covering the full extension -> Native Messaging -> DB -> CLI pipeline across 3 sources.

### Changed
- **ConversationTurn model** — added `tool_names` and `error_text` fields for richer agent analysis (backward-compatible defaults)
- **Claude Code adapter** — now extracts individual tool names (Read, Edit, Bash, etc.) from tool_use blocks, not just counts
- **Suggestions** — `distill` now suggests `reprompt agent`; `agent` suggests `--loops-only` and `privacy --deep`
- Tests: 1397 -> 1490+

## [1.5.0] - 2026-03-25

### Added
- **Instant dashboard** — bare `reprompt` now shows a health overview: total prompts, sessions, avg score, top categories, recent activity. Zero-state guides new users; data-state gives at-a-glance intelligence
- **Session type detection** — `distill` auto-classifies sessions (debugging, feature-dev, exploration, refactoring, config, learning) and adapts signal weights per type
- **Hook suggestion throttle** — `reprompt scan` suggests `install-hook` only once, not every run

### Changed
- **Command consolidation (23 → 20)** — deprecated `library`, `recommend`, `trends` as standalone commands; functionality absorbed into `report --smart` and `style --trends` flags
- **Signal quality improvements** — reduced false positives in position, length, and error_recovery signals for more accurate distillation
- Tests: 1350 → 1397

### Deprecated
- `reprompt library` → use `reprompt report --smart`
- `reprompt recommend` → use `reprompt insights`
- `reprompt trends` → use `reprompt style --trends`

## [1.4.1] - 2026-03-25

### Added
- **`compare --best-worst`** — auto-selects your highest and lowest scoring prompts from the database for instant comparison
- **`style --trends`** — period-over-period style fingerprint comparison showing how your prompting patterns evolve

## [1.4.0] - 2026-03-24

### Added
- **Context recovery** — `distill --export` generates a markdown summary of conversation context, ready to paste into a new session when context is lost
- **`--full` mode** — exports all turns (not just important ones) for complete session records
- **`--show-weights` / `--weights`** — transparent signal weighting so you can see and tune how importance is scored
- **Template sub-app** — `reprompt template save|list|use` for managing reusable prompts
- **Enhanced insights** — effectiveness scoring and similar prompt suggestions

### Changed
- **Command consolidation (27 → 23)** — deprecated `save`, `templates`, `use`, `effectiveness`, `merge-view` in favor of unified `template` and `insights` commands
- Tests: 1250 → 1350

### Deprecated
- `reprompt save` → use `reprompt template save`
- `reprompt templates` → use `reprompt template list`
- `reprompt use` → use `reprompt template use`
- `reprompt effectiveness` → folded into `reprompt insights`
- `reprompt merge-view` → use `reprompt report --smart`

## [1.3.1] - 2026-03-23

### Added
- **Actionable suggestions** — 5 core commands now show contextual "→ Try:" hints guiding users to the next useful command
- **`--source` consistency** — all data commands support `--source` filtering

### Fixed
- System-injected XML prompts (starting with `<`) filtered from distillation input

## [1.3.0] - 2026-03-23

### Added
- **Conversation distillation** — `reprompt distill` extracts the most important turns from AI conversations using 6-signal importance scoring: position, length, tool trigger, error recovery, semantic shift, uniqueness
- **Full conversation parsing** — adapters now return both user and assistant turns (Claude Code and ChatGPT have full implementations; others fall back to user-only)
- **Rule-based summaries** — `--summary` generates compressed conversation overviews without requiring an LLM
- **Flexible session selection** — `--last N` for recent sessions, `--threshold` to control importance cutoff
- **Output options** — `--json`, `--copy` for pipeline integration

### Changed
- Tests: 1153 → 1217

## [1.2.0] - 2026-03-23

### Added
- **4-layer prompt compression** — `reprompt compress` optimizes prompts through character normalization, phrase simplification (40+ zh / 50+ en rules), filler word deletion (jieba-aware), and structure cleanup
- **Compressibility in PromptDNA** — every scanned prompt gets a compressibility score, visible in insights and HTML dashboard
- **`--copy` flag** — compressed output copies to clipboard

### Changed
- Tests: 1046 → 1153

### Research
- Compression rules based on LLMLingua (Microsoft), CompactPrompt, TSC, stopwords-iso/zh, Prompt Report 2406.06608

## [1.1.0] - 2026-03-22

### Added
- **Privacy exposure analysis** — `reprompt privacy` shows what data you've sent to which AI tools: file paths, error messages, code snippets, personal identifiers
- **Per-adapter breakdown** — see privacy exposure grouped by source (Claude Code vs ChatGPT vs Cursor etc.)
- **Instruction repetition scoring** — detects and scores redundant instructions within prompts
- **Per-source insights** — `reprompt insights --source` shows patterns specific to each tool

### Changed
- Tests: 923 → 1046

## [1.0.0] - 2026-03-16

### Changed
- **Stability release** — no new features, focused on reliability and trust
- Empty-state guidance for `report` and `digest` commands
- Scan shows "Try next" hints for new users
- Feature extraction errors logged instead of silently swallowed

### Infrastructure
- DB schema versioning via `PRAGMA user_version` — ordered migrations, no more ad-hoc ALTER TABLE
- CI enforces ≥90% test coverage; publish workflow runs tests before PyPI upload
- Removed unused `[science]` optional dependency group
- CHANGELOG backfill for all versions since v0.7.4

## [0.9.3] - 2026-03-16

### Added
- `reprompt report --source` and `reprompt search --source` — filter by source adapter

## [0.9.2] - 2026-03-15

### Added
- **Wrapped reports** — `reprompt wrapped` generates an annual Prompt DNA report (terminal, HTML, shareable)
- **6 prompt personas** — Architect, Debugger, Explorer, Novelist, Sniper, Teacher (auto-classified)
- **Telemetry** — opt-in anonymous 26-dimension feature vectors (no prompt text, no PII)
- **Share** — HMAC-SHA256 signed upload to getreprompt.dev/api/share
- Open-core plugin system: `entry_points(group="reprompt.plugins")` loaded at startup

### Changed
- Migrated wrapped, personas, telemetry, share into open-source CLI (from reprompt-pro)

## [0.9.1] - 2026-03-14

### Added
- **Multi-language PromptDNA** — Chinese feature extraction via jieba (optional `[chinese]` extra)
- **Native messaging bridge** — Chrome/Firefox extension support (`reprompt install-extension`)
- **Style fingerprint** — `reprompt style` shows personal prompting patterns
- **Template variables** — `reprompt use template_name key=value` with `{placeholder}` substitution
- **Enhanced recommendations** — `reprompt recommend` uses effectiveness data

### Infrastructure
- Plugin system for open-core architecture (reprompt-pro registers via entry_points)
- DB aggregation queries for plugin data access

## [0.9.0] - 2026-03-13

### Added
- **ChatGPT import** — `reprompt import conversations.json` parses OpenAI export format
- **Claude.ai import** — `reprompt import claude-export.zip` parses Claude web chat exports
- **`reprompt import` command** — unified import with auto-detection of source format
- 7 non-coding prompt categories for Chat AI support (brainstorm, summarize, explain, translate, roleplay, creative, casual)

### Changed
- Tests: 580 → 680+

## [0.8.2] - 2026-03-13

### Added
- **Digest category deltas** — `reprompt digest` shows per-category % change with arrows
- **`reprompt digest --history`** — view past digest log entries

## [0.8.1] - 2026-03-12

### Added
- **HTML dashboard** — `reprompt report --html` generates interactive Chart.js dashboard
- Digest + cluster data wired into HTML report

## [0.8.0] - 2026-03-12

### Added
- **Effectiveness columns** — `prompts.effectiveness_score`, `prompt_patterns.effectiveness_avg`
- **`reprompt library`** shows Eff column with score + star rating
- **`reprompt digest`** shows avg session quality
- **OpenClaw `parse_session_meta()`** — session quality scoring for OpenClaw/OpenCode sessions
- `db.update_prompt_effectiveness()` and `db.compute_pattern_effectiveness()` methods
- Pipeline: `run_scan()` propagates session scores to prompts; `build_report_data()` recomputes pattern averages

### Infrastructure
- `_migrate_v08()` adds effectiveness columns via safe ALTER TABLE

### Changed
- Tests: 480 → 510+

## [0.7.5] - 2026-03-12

### Added
- Expanded Chinese stop words — 65 function words from stopwords-iso added

## [0.7.4] - 2026-03-12

### Improved
- **Mixed Chinese/English tokenization** — Hot Phrases now uses a custom analyzer that handles code-switching text natively: Chinese character runs emit bigrams (报错, 修复, 自动化 etc.), ASCII words use standard tokenization. Zero extra dependencies (regex only)
- **Chinese stop words** (~90 words, HIT + cn_stopwords) — common Chinese particles, pronouns, conjunctions, discourse markers (好的, 是否, 或者, 现在, 项目, 代码 etc.) are now filtered. Eliminates single-char noise like 们/现/个/么 from Hot Phrases
- **English conversational stop words** (sklearn gap fill) — sklearn's built-in list (Stone 2010, formal text) misses common chat words: `does`, `yeah`, `ok`, `gotcha`, `doesn`, `wouldn`, `really`, `maybe`, `also` etc. These are now filtered
- **AI tool names as stop words** — `claude`, `cursor`, `aider`, `gemini` are generic for their own users and no longer pollute Hot Phrases
- **Chinese bigrams only** — single Chinese characters are almost always stop words or partial words (们 only in 我们, 么 only in 什么); removing unigram emission keeps the phrase table semantically meaningful

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
