# `re:prompt`

**Grammarly for Prompts** -- analyze your AI conversations with research-backed scoring.

[![PyPI version](https://img.shields.io/pypi/v/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/reprompt-cli)](https://pypi.org/project/reprompt-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-923-brightgreen)](https://github.com/reprompt-dev/reprompt)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](https://github.com/reprompt-dev/reprompt)

---

## See it in action

```bash
$ pip install reprompt-cli
$ reprompt scan --source claude-code
  Scanning 890 sessions... Found 1,063 prompts (295 unique)

$ reprompt score "Fix the auth bug in src/login.ts where JWT expires"
  Score: 74/100
  Structure: 18/25 | Context: 22/25 | Position: 15/20 | Repetition: 9/15 | Clarity: 10/15
  Tip: Add the error message for +15% accuracy

$ reprompt wrapped --share
  Your Prompt DNA: Architect (Score 78, better than 72% of prompters)
  Share link: https://getreprompt.dev/w/abc123
```

## What it does

| Command | Description |
|---------|-------------|
| `reprompt scan` | Scan 8+ AI tools for prompts (Claude Code, Cursor, Aider, Gemini CLI, Cline, OpenClaw, ChatGPT, Claude.ai) |
| `reprompt score` | Instant 0-100 scoring with 30+ research-backed features |
| `reprompt compare` | Side-by-side analysis of two prompts |
| `reprompt wrapped` | Your Prompt DNA report -- persona, scores, shareable card |
| `reprompt insights` | Personal patterns vs research-optimal |
| `reprompt digest` | Weekly summary comparing current vs previous period |
| `reprompt report` | Full analytics with hot terms, clusters, patterns |
| `reprompt library` | Auto-extracted prompt patterns and templates |

## Prompt Science

Scoring is based on 4 research papers (Google, Stanford, EMNLP, Prompt Report) covering 30+ features across 5 dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| **Structure** | Markdown formatting, code blocks, explicit constraints |
| **Context** | File paths, error messages, technical specificity |
| **Position** | Instruction placement relative to context |
| **Repetition** | Redundancy that degrades model attention |
| **Clarity** | Readability, sentence length, ambiguity |

All analysis runs locally in <1ms per prompt. No LLM calls, no network requests.

## Supported AI tools

| Tool | Format | Session location |
|------|--------|-----------------|
| Claude Code | JSONL | `~/.claude/projects/` |
| Cursor | .vscdb | `~/Library/Application Support/Cursor/User/` |
| Aider | Markdown | `.aider.chat.history.md` |
| Gemini CLI | JSON | `~/.gemini/tmp/` |
| Cline (VS Code) | JSON | `globalStorage/saoudrizwan.claude-dev/` |
| OpenClaw / OpenCode | JSON | `~/.openclaw/` / `~/.opencode/sessions/` |
| ChatGPT | JSON | `conversations.json` export |
| Claude.ai | JSON/ZIP | Web chat export |

## Installation

```bash
pip install reprompt-cli          # core
pip install reprompt-cli[chinese] # + Chinese prompt support
pip install reprompt-cli[mcp]     # + MCP server for Claude Code / Continue.dev / Zed
```

## Privacy

- All analysis runs locally. No prompts leave your machine.
- Optional telemetry sends only anonymous 26-dimension feature vectors -- never prompt text.
- Open source: audit exactly what's collected.

[Privacy policy](https://getreprompt.dev/privacy)

## Links

- **Website:** [getreprompt.dev](https://getreprompt.dev)
- **PyPI:** [reprompt-cli](https://pypi.org/project/reprompt-cli/)
- **Privacy:** [getreprompt.dev/privacy](https://getreprompt.dev/privacy)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
