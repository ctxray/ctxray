# `re:prompt`

**Analyze what you type into AI tools** -- prompt scoring, agent error loops, leaked credential detection, conversation distillation.

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
$ reprompt
  ╭─ Prompt Dashboard ─────────────────────────────────────────╮
  │  Prompts: 1,063 (295 unique)   Sessions: 890              │
  │  Avg Score: 68/100             Top: debug (31%), impl (24%)│
  │  Sources: claude-code, cursor, chatgpt                     │
  ╰────────────────────────────────────────────────────────────╯

$ reprompt score "Fix the auth bug in src/login.ts where JWT expires"
  Score: 74/100
  Structure: 18/25 | Context: 22/25 | Position: 15/20 | Repetition: 9/15 | Clarity: 10/15
  Tip: Add the error message for +15% accuracy

$ reprompt distill --last 3 --summary
  Session: feature-dev (42 turns, 18 important)
  Key moments: initial spec → auth module → test failures → JWT fix → passing
  Context: "Building auth system with JWT refresh tokens for Express API"

$ reprompt compress "请帮我看一下这个代码，就是那个 login 的那个文件，好像有点问题"
  Before: 31 tokens → After: 15 tokens (52% saved)
  "看一下 login 文件的问题"
```

## What it does

### Analyze

| Command | Description |
|---------|-------------|
| `reprompt` | Instant dashboard -- prompts, sessions, avg score, top categories |
| `reprompt scan` | Auto-discover prompts from 9 AI tools |
| `reprompt score "prompt"` | Research-backed 0-100 scoring with 30+ features |
| `reprompt compare "a" "b"` | Side-by-side prompt analysis (or `--best-worst` for auto-selection) |
| `reprompt insights` | Personal patterns vs research-optimal benchmarks |
| `reprompt style` | Prompting fingerprint with `--trends` for evolution tracking |
| `reprompt agent` | Agent workflow analysis -- error loops, tool patterns, session efficiency |

### Optimize

| Command | Description |
|---------|-------------|
| `reprompt compress "prompt"` | 4-layer prompt compression (50%+ token savings typical) |
| `reprompt distill` | Extract important turns from conversations with 6-signal scoring |
| `reprompt distill --export` | Recover context when a session runs out -- paste into new session |
| `reprompt lint` | Prompt quality linter with GitHub Action support |

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
reprompt scan                       # discover prompts from installed AI tools
reprompt                            # see your dashboard
reprompt score "your prompt here"   # score any prompt instantly
reprompt distill --last 1           # distill your most recent conversation
```

### Auto-scan after every session

```bash
reprompt install-hook               # adds post-session hook to Claude Code
```

### Browser extension

Capture prompts from ChatGPT, Claude.ai, and Gemini directly in your browser:

1. **Install the extension** from [Chrome Web Store](https://chromewebstore.google.com/detail/reprompt/ojdccpagaanchmkninlbgbgemdcjckhn)
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
```

#### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/reprompt-dev/reprompt
    rev: v1.6.0
    hooks:
      - id: reprompt-lint
```

#### Direct CLI

```bash
reprompt lint --score-threshold 50  # exit 1 if avg score < 50
reprompt lint --strict              # exit 1 on warnings
reprompt lint --json                # machine-readable output
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
- **PyPI:** [reprompt-cli](https://pypi.org/project/reprompt-cli/)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **Privacy:** [getreprompt.dev/privacy](https://getreprompt.dev/privacy)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
