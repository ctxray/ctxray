# Contributing to reprompt

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
5. Run `mypy src/reprompt/` — must pass clean
6. Submit a PR with a clear description

## Adding Adapters

To add support for a new AI coding tool:

1. Create `src/reprompt/adapters/your_tool.py`
2. Subclass `BaseAdapter`
3. Implement `parse_session()` and `detect_installed()`
4. Add test fixtures in `tests/fixtures/`
5. Add tests in `tests/test_adapter_your_tool.py`

## Architecture

```
src/reprompt/
├── cli.py              # Typer CLI entry point
├── config.py           # pydantic-settings configuration
├── core/               # Business logic
│   ├── models.py       # Prompt dataclass
│   ├── dedup.py        # Two-layer deduplication
│   ├── analyzer.py     # TF-IDF + K-means
│   ├── library.py      # Pattern extraction
│   └── pipeline.py     # Orchestrator
├── adapters/           # AI tool parsers
├── embeddings/         # Pluggable backends
├── storage/            # SQLite layer
└── output/             # Report formatters
```
