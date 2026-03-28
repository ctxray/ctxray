# Contributing to reprompt

Thanks for your interest in contributing! reprompt is an open-source prompt intelligence tool, and contributions of all kinds are welcome.

## Quick Links

- [Good First Issues](https://github.com/reprompt-dev/reprompt/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
- [Help Wanted](https://github.com/reprompt-dev/reprompt/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)

## Development Setup

```bash
git clone https://github.com/reprompt-dev/reprompt
cd reprompt
uv venv
uv pip install -e ".[dev]"
```

## Running Tests

```bash
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=reprompt  # with coverage
```

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Type Checking

We use [mypy](https://mypy-lang.org/) in strict mode:

```bash
uv run mypy src/reprompt/
```

## Pull Requests

1. Fork the repo and create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass and coverage doesn't decrease
4. Run `ruff check` and `ruff format`
5. Run `mypy src/reprompt/` -- must pass clean
6. Submit a PR with a clear description

## Common Contribution Areas

### Adding Adapters (new AI tool support)

Adding a new adapter is the easiest way to contribute. Each adapter is ~50-100 lines:

1. Create `src/reprompt/adapters/your_tool.py`
2. Subclass `BaseAdapter` from `adapters/base.py`
3. Implement:
   - `name` property -- adapter identifier (e.g., `"copilot"`)
   - `default_session_path` -- where the tool stores sessions
   - `discover_sessions()` -- find session files
   - `parse_session(path)` -- extract `Prompt` objects
   - Optional: `parse_conversation(path)` -- extract full conversation turns
4. Register in `core/pipeline.py` → `get_adapters()`
5. Add tests in `tests/test_your_tool_adapter.py`

**Reference adapters:**
- `adapters/cline.py` -- simplest (~80 lines, JSON format)
- `adapters/aider.py` -- markdown parsing
- `adapters/cursor.py` -- SQLite/vscdb format

### Adding Lint Rules

Each lint rule is a standalone function in `core/lint.py`:

1. Add your rule check in `lint_prompt()`
2. Return a `LintViolation` with `severity="error"` or `"warning"`
3. Add tests in `tests/test_lint.py`

### Adding Privacy Patterns

Extend sensitive content detection in `core/privacy_scan.py`:

1. Add a regex pattern to the `PATTERNS` dict
2. Add category mapping in `CATEGORY_MAP`
3. Add safety filter if needed (to exclude false positives)
4. Add tests in `tests/test_privacy_scan.py`

## Architecture

```
src/reprompt/
├── cli.py              # Typer CLI (21 commands)
├── config.py           # pydantic-settings configuration
├── core/               # Business logic
│   ├── models.py       # Prompt dataclass
│   ├── scorer.py       # Research-calibrated 0-100 scoring
│   ├── lint.py         # Quality linter
│   ├── compress.py     # 4-layer prompt compression
│   ├── distill.py      # Conversation distillation
│   ├── agent.py        # Agent workflow analysis
│   ├── privacy_scan.py # Sensitive content detection
│   └── pipeline.py     # Orchestrator
├── adapters/           # 9 AI tool parsers
├── storage/            # SQLite layer
├── bridge/             # Browser extension Native Messaging
└── output/             # Report formatters (terminal, JSON, HTML)
```

## Questions?

Open an issue or start a discussion. We're happy to help you get started.
