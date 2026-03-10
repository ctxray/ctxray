"""Configuration with env var override support."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


def _default_db_path() -> str:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", "~"))
    elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
        base = Path("~/Library/Application Support")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
    return str(base / "reprompt" / "reprompt.db")


class Settings(BaseSettings):
    model_config = {"env_prefix": "REPROMPT_"}

    # Embedding
    embedding_backend: str = "tfidf"
    ollama_url: str = "http://localhost:11434"

    # Storage
    db_path: Path = Path(os.path.expanduser(_default_db_path()))

    # Dedup
    dedup_threshold: float = 0.85

    # Library
    library_min_frequency: int = 3
    library_categories: list[str] = [
        "debug",
        "implement",
        "review",
        "test",
        "refactor",
        "explain",
        "config",
    ]
