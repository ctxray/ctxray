# `re:prompt`

**Score, rewrite, and optimize your AI prompts** -- the only CLI that improves your prompts automatically. No LLM needed.

[![PyPI version](https://img.shields.io/pypi/v/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/reprompt-dev/reprompt/actions)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](https://github.com/reprompt-dev/reprompt)

---

![reprompt demo](docs/demo.gif)

## See it in action

```bash
$ pip install reprompt-cli

# Rewrite a weak prompt into a better one (no LLM, rule-based)
$ reprompt rewrite "I was wondering if you could maybe help me fix the auth bug"
  34 → 52 (+18)

  ╭─ Rewritten ────────────────────────────────────────────────╮
  │ Help me fix the auth bug.                                  │
  ╰────────────────────────────────────────────────────────────╯

  Changes
  ✓ Removed filler (24% shorter)
  ✓ Removed hedging language

  You should also
  → Add actual code snippets or error messages for context
  → Reference specific files or functions by name
  → Add constraints (e.g., "Do not modify existing tests")

# Full diagnostic in one command
$ reprompt check "Fix the auth bug in src/login.ts where JWT expires"
  GOOD · 58

  Clarity     ████████████░░░░░░░░ 15/25
  Context     ████████████████░░░░ 20/25
  Position    ████████████████████ 20/20
  Structure   ░░░░░░░░░░░░░░░░░░░░  0/15
  Repetition  ███░░░░░░░░░░░░░░░░░  3/15

  Strengths
  ✓ Key instruction at the start — optimal placement
  ✓ References specific files

  Improve
  → Add the actual error message (+6 pts)
  → Add constraints like "Don't modify tests" (+5 pts)
```

## What it does

### Analyze

| Command | Description |
|---------|-------------|
| `reprompt` | Instant dashboard -- prompts, sessions, avg score, top categories |
| `reprompt scan` | Auto-discover prompts from 9 AI tools |
| `reprompt check "prompt"` | **Full diagnostic** -- score + lint + rewrite preview in one command |
| `reprompt score "prompt"` | Research-backed 0-100 scoring with 30+ features |
| `reprompt compare "a" "b"` | Side-by-side prompt analysis (or `--best-worst` for auto-selection) |
| `reprompt insights` | Personal patterns vs research-optimal benchmarks |
| `reprompt style` | Prompting fingerprint with `--trends` for evolution tracking |
| `reprompt agent` | Agent workflow analysis -- error loops, tool patterns, session efficiency |
| `reprompt sessions` | Session quality scores with frustration signal detection |
| `reprompt repetition` | Cross-session repetition detection -- spot recurring prompts |
| `reprompt projects` | Per-project quality breakdown -- sessions, scores, frustration signals |

### Optimize

| Command | Description |
|---------|-------------|
| `reprompt build "task"` | **Build prompts from components** -- task, context, files, errors, constraints. Model-aware (Claude/GPT/Gemini) |
| `reprompt rewrite "prompt"` | **Rewrite prompts to score higher** -- filler removal, restructuring, hedging cleanup |
| `reprompt compress "prompt"` | 4-layer prompt compression (40-60% token savings typical) |
| `reprompt distill` | Extract important turns from conversations with 6-signal scoring |
| `reprompt distill --export` | Recover context when a session runs out -- paste into new session |
| `reprompt lint` | Configurable prompt quality linter with CI/GitHub Action support |
| `reprompt init` | Generate `.reprompt.toml` config for your project |

### Manage

| Command | Description |
|---------|-------------|
| `reprompt privacy` | See what data you sent where -- file paths, errors, PII exposure |
| `reprompt privacy --deep` | Scan for sensitive content: API keys, tokens, passwords, PII |
| `reprompt report` | Full analytics: hot phrases, clusters, patterns (`--html` for dashboard) |
| `reprompt digest` | Weekly summary comparing current vs previous period |
| `reprompt wrapped` | Prompt DNA report -- persona, scores, shareable card |
| `reprompt template save\|list\|use` | Save and reuse your best prompts |

## Prompt Science

Scoring is calibrated against 4 research papers covering 30+ features across 5 dimensions:

| Dimension | What it measures | Paper |
|-----------|-----------------|-------|
| **Structure** | Markdown, code blocks, explicit constraints | Prompt Report 2406.06608 |
| **Context** | File paths, error messages, technical specificity | Google 2512.14982 |
| **Position** | Instruction placement relative to context | Stanford 2307.03172 |
| **Repetition** | Redundancy that degrades model attention | Google 2512.14982 |
| **Clarity** | Readability, sentence length, ambiguity | SPELL (EMNLP 2023) |

All analysis runs locally in <1ms per prompt. No LLM calls, no network requests.

## Conversation Distillation

`reprompt distill` scores every turn in a conversation using 6 signals:

- **Position** -- first/last turns carry framing and conclusions
- **Length** -- substantial turns contain more information
- **Tool trigger** -- turns that cause tool calls are action-driving
- **Error recovery** -- turns that follow errors show problem-solving
- **Semantic shift** -- topic changes mark conversation boundaries
- **Uniqueness** -- novel phrasing vs repetitive follow-ups

Session type (debugging, feature-dev, exploration, refactoring) is auto-detected and signal weights adapt accordingly.

## Supported AI tools

| Tool | Format | Auto-discovered by `scan` |
|------|--------|--------------------------|
| Claude Code | JSONL | Yes |
| Codex CLI | JSONL | Yes |
| Cursor | .vscdb | Yes |
| Aider | Markdown | Yes |
| Gemini CLI | JSON | Yes |
| Cline (VS Code) | JSON | Yes |
| OpenClaw / OpenCode | JSON | Yes |
| ChatGPT | JSON | Via `reprompt import` |
| Claude.ai | JSON/ZIP | Via `reprompt import` |

## Installation

```bash
pip install reprompt-cli            # core (all features, zero config)
pip install reprompt-cli[chinese]   # + Chinese prompt analysis (jieba)
pip install reprompt-cli[mcp]       # + MCP server for Claude Code / Continue.dev / Zed
```

### Quick start

```bash
reprompt check "your prompt here"   # full diagnostic — score + lint + rewrite
reprompt scan                       # discover prompts from installed AI tools
reprompt                            # see your dashboard
```

### Auto-scan after every session

```bash
reprompt install-hook               # adds post-session hook to Claude Code
```

### Browser extension

Capture prompts from ChatGPT, Claude.ai, and Gemini directly in your browser. Live score badge shows prompt quality as you type.

1. **Install the extension** from [Chrome Web Store](https://chromewebstore.google.com/detail/reprompt/ojdccpagaanchmkninlbgbgemdcjckhn) or [Firefox Add-ons](https://addons.mozilla.org/addon/reprompt-cli/)
2. **Connect to the CLI:** `reprompt install-extension`
3. **Verify:** `reprompt extension-status`

Captured prompts sync locally via Native Messaging -- nothing leaves your machine.

### CI integration

#### GitHub Action

```yaml
# .github/workflows/prompt-lint.yml
- uses: reprompt-dev/reprompt@main
  with:
    score-threshold: 50   # fail if avg prompt score < 50
    strict: true          # fail on warnings too
    comment-on-pr: true   # post quality report as PR comment
```

#### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/reprompt-dev/reprompt
    rev: v2.2.2
    hooks:
      - id: reprompt-lint
```

#### Direct CLI

```bash
reprompt lint --score-threshold 50  # exit 1 if avg score < 50
reprompt lint --strict              # exit 1 on warnings
reprompt lint --json                # machine-readable output
```

#### Project configuration

```bash
reprompt init   # generates .reprompt.toml with all rules documented
```

```toml
# .reprompt.toml (or [tool.reprompt.lint] in pyproject.toml)
[lint]
score-threshold = 50       # fail if avg score < 50

[lint.rules]
min-length = 20            # error if prompt < 20 chars (0 = off)
short-prompt = 40          # warning if < 40 chars (0 = off)
vague-prompt = true        # error on "fix it" etc (false = off)
debug-needs-reference = true
```

## Privacy

- All analysis runs locally. No prompts leave your machine.
- `reprompt privacy` shows exactly what you've sent to which AI tool.
- Optional telemetry sends only anonymous 26-dimension feature vectors -- never prompt text.
- Open source: audit exactly what's collected.

[Privacy policy](https://getreprompt.dev/privacy)

## Links

- **Website:** [getreprompt.dev](https://getreprompt.dev)
- **Chrome Extension:** [Chrome Web Store](https://chromewebstore.google.com/detail/reprompt/ojdccpagaanchmkninlbgbgemdcjckhn)
- **Firefox Add-on:** [Firefox Add-ons](https://addons.mozilla.org/addon/reprompt-cli/)
- **PyPI:** [reprompt-cli](https://pypi.org/project/reprompt-cli/)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **Privacy:** [getreprompt.dev/privacy](https://getreprompt.dev/privacy)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
